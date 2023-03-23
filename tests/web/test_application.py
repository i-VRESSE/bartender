from asyncio import sleep
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator
from zipfile import ZipFile

import jwt
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from httpx._types import RequestFiles
from starlette import status


@pytest.mark.anyio
async def test_list_applications(
    fastapi_app: FastAPI,
    client: AsyncClient,
) -> None:
    url = fastapi_app.url_path_for("list_applications")
    response = await client.get(url)
    apps = response.json()
    assert apps == ["app1"]


@pytest.mark.anyio
async def test_get_application(
    fastapi_app: FastAPI,
    client: AsyncClient,
) -> None:
    url = fastapi_app.url_path_for("get_application", application="app1")

    response = await client.get(url)
    app = response.json()

    expected = {
        "command": "wc $config",
        "config": "job.ini",
        "allowed_roles": [],
    }
    assert app == expected


@pytest.mark.anyio
async def test_upload(
    fastapi_app: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    auth_headers: Dict[str, str],
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
async def test_upload_with_role_granted(
    current_user_with_role: None,
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
    auth_headers: Dict[str, str],
) -> None:
    url = app_with_roles.url_path_for("upload_job", application="app1")
    with prepare_form_data(tmp_path) as files:
        response = await client.put(url, files=files, headers=auth_headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Missing role" in response.text


def assert_job_dir(job_root_dir: Path, job_id: str) -> None:  # noqa: WPS218
    job_dir = job_root_dir / job_id
    meta_job_id, meta_job_token = (job_dir / "meta").read_text().splitlines()
    assert meta_job_id == job_id
    assert jwt_decode(meta_job_token)
    assert (job_dir / "job.ini").read_text() == "# Example config file"
    assert (job_dir / "input.csv").read_text() == "# Example input data file"
    assert (job_dir / "stdout.txt").read_text() == " 0  4 21 job.ini\n"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "returncode").read_text() == "0"


def jwt_decode(token: str) -> Dict[str, Any]:
    # value from fastapi_app fixture
    key = "testsecret"
    # values from fastapi_users.authentication.JWTStrategy
    audience = ["fastapi-users:auth"]
    algorithms = ["HS256"]
    return jwt.decode(token, key, audience=audience, algorithms=algorithms)


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
