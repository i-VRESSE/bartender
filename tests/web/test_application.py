from asyncio import sleep
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.datastructures import FormData
from httpx import AsyncClient
from httpx._types import RequestFiles
from starlette import status

from bartender.config import ApplicatonConfiguration
from bartender.context import Context, get_context
from bartender.destinations import Destination
from bartender.filesystems.local import LocalFileSystem
from bartender.schedulers.eager import EagerScheduler, EagerSchedulerConfig
from bartender.web.api.applications.submit import build_description
from bartender.web.api.applications.views import (
    extract_payload_from_form,
    validate_input,
)


@pytest.mark.anyio
async def test_upload(
    fastapi_app: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    auth_headers: Dict[str, str],
    current_user_token: str,
) -> None:
    """Test upload of a job archive."""
    url = fastapi_app.url_path_for("upload_job", application="app1")
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=auth_headers)

    jurl = response.headers["location"]
    assert response.status_code == status.HTTP_303_SEE_OTHER

    job = await wait_for_job_completion(client, jurl, auth_headers)

    assert job["state"] == "ok"

    assert_job_dir(job_root_dir, str(job["id"]))


@pytest.mark.anyio
async def test_upload_with_input_schema(
    app_with_input_schema: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    auth_headers: Dict[str, str],
) -> None:
    url = app_with_input_schema.url_path_for("upload_job", application="app1")
    data = {"message": "hello"}
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, data=data, headers=auth_headers)

    jurl = response.headers["location"]
    assert response.status_code == status.HTTP_303_SEE_OTHER

    job = await wait_for_job_completion(client, jurl, auth_headers)

    assert job["state"] == "ok"
    job_dir = job_root_dir / str(job["id"])
    assert (job_dir / "stdout.txt").read_text() == "hello\n"


@pytest.mark.anyio
async def test_upload_with_role_granted(
    fastapi_app: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    auth_headers: Dict[str, str],
) -> None:
    url = fastapi_app.url_path_for("upload_job", application="app1")
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=auth_headers)

    assert response.status_code == status.HTTP_303_SEE_OTHER


@pytest.mark.anyio
async def test_upload_with_no_role_granted(
    app_with_roles: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    second_user_token: str,
) -> None:
    url = app_with_roles.url_path_for("upload_job", application="app1")
    headers = {"Authorization": f"Bearer {second_user_token}"}
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Missing role" in response.text


@pytest.mark.anyio
async def test_upload_invalid_application(
    fastapi_app: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
    auth_headers: Dict[str, str],
) -> None:
    """Test upload of a job archive."""
    url = fastapi_app.url_path_for("upload_job", application="appzzzzzzzz")
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=auth_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid application" in response.text


@pytest.mark.anyio
async def test_upload_submission_error(
    fastapi_app: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
    auth_headers: Dict[str, str],
) -> None:
    context = Context(
        job_root_dir=tmp_path,
        destination_picker=lambda _, _1, _2, _3: "eager",  # noqa: WPS111
        applications={
            "app1": ApplicatonConfiguration(
                command_template="exit 42",
            ),
        },
        destinations={
            "eager": Destination(
                scheduler=EagerScheduler(EagerSchedulerConfig(max_load=100)),
                filesystem=LocalFileSystem(),
            ),
        },
    )

    fastapi_app.dependency_overrides[get_context] = lambda: context
    url = fastapi_app.url_path_for("upload_job", application="app1")
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=auth_headers)

    # Submission to scheduler is done in background task,
    # so direct response is OK, but job state will be error
    jurl = response.headers["location"]
    assert response.status_code == status.HTTP_303_SEE_OTHER

    job = await wait_for_job_completion(client, jurl, auth_headers)
    assert job["state"] == "error"
    assert (tmp_path / str(job["id"]) / "returncode").read_text() == "42"


def assert_job_dir(
    job_root_dir: Path,
    job_id: str,
) -> None:
    job_dir = job_root_dir / job_id
    assert (job_dir / "job.ini").read_text() == "# Example config file"
    assert (job_dir / "input.csv").read_text() == "# Example input data file"
    assert (job_dir / "stdout.txt").read_text() == " 0  4 21 job.ini\n"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "returncode").read_text() == "0"


async def wait_for_job_completion(
    client: AsyncClient,
    jurl: str,
    auth_headers: Dict[str, str],
) -> Dict[str, Any]:
    job = None
    index = 0
    while index < 10:
        jresponse = await client.get(jurl, headers=auth_headers)
        job = jresponse.json()
        if job["state"] in {"ok", "error"}:
            break
        await sleep(0.1)
        index += 1
    else:
        pytest.fail("Waiting for job completion took too long")
    return job


def create_test_archive(tmp_path: Path) -> Path:
    archive_fn = tmp_path / "upload.zip"
    archive = ZipFile(archive_fn, mode="w")
    archive.writestr("job.ini", "# Example config file")
    archive.writestr("input.csv", "# Example input data file")
    archive.close()
    return archive_fn


@contextmanager
def prepare_form_data(
    tmp_path: Path,
) -> Generator[RequestFiles, None, None]:
    archive_fn = create_test_archive(tmp_path)
    with open(archive_fn, "rb") as archive_file:
        yield {
            "upload": (
                "upload.zip",
                archive_file.read(),
                "application/zip",
            ),
        }


@pytest.mark.skip(reason="Cannot handle non-string types")
def test_complex_nested_schema(
    tmp_path: Path,
) -> None:
    cmd = "tar {% if auto %}-a{% endif %} --level {{ level }} "
    cmd += "-cf {{ output }} {{ input|join(' ')|q }}"  # noqa: WPS336
    config = ApplicatonConfiguration(
        command_template=cmd,
        input_schema={
            "type": "object",
            "properties": {
                "level": {"type": "integer", "default": 6},
                "input": {"type": "array", "items": {"type": "string"}},
                "output": {"type": "string"},
                "auto": {"type": "boolean", "default": False},
            },
            "required": ["output"],
        },
    )
    data = FormData(
        {
            "level": "9",
            "input": '["foo.txt", "bar.txt"]',
            "output": "archive.tar",
            "auto": "true",
        },
    )
    payload = extract_payload_from_form(data)
    validate_input(config, payload)
    description = build_description(
        tmp_path,
        payload,
        config,
    )

    assert description.command == "tar -a --level 9 -cf archive.tar foo.txt bar.txt"
