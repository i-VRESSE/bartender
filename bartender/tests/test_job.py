import uuid
from asyncio import sleep
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.db.dao.job_dao import JobDAO
from bartender.web.users.manager import current_api_token


@pytest.fixture
def mock_current_api_token(fastapi_app: FastAPI) -> str:
    """Tests require logged in user and their api token, mock it here.

    :param fastapi_app: The app to override in
    :return: A dummy API token
    """
    token = "mytoken"  # noqa: S105
    fastapi_app.dependency_overrides[current_api_token] = lambda: token
    return token


@pytest.mark.anyio
async def test_getting_all(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
    job_root_dir: Path,
    mock_current_api_token: str,
) -> None:
    """Test the retrieval of all jobs."""
    retrieve_url = fastapi_app.url_path_for("retrieve_jobs")
    response = await client.get(retrieve_url)
    json_response = response.json()
    assert not len(json_response)
    create_url = fastapi_app.url_path_for("create_job")
    test_name = uuid.uuid4().hex
    response = await client.put(
        create_url,
        json={
            "name": test_name,
        },
    )
    jobid = int(response.headers["location"].split("/")[-1])
    assert response.status_code == status.HTTP_303_SEE_OTHER

    response = await client.get(retrieve_url)

    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response[0]["id"] == jobid
    assert json_response[0]["name"] == test_name


@pytest.mark.anyio
async def test_creation(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
    job_root_dir: Path,
    mock_current_api_token: str,
) -> None:
    """Tests job instance creation."""
    url = fastapi_app.url_path_for("create_job")
    test_name = uuid.uuid4().hex

    response = await client.put(
        url,
        json={
            "name": test_name,
        },
    )

    assert response.status_code == status.HTTP_303_SEE_OTHER
    jobid = int(response.headers["location"].split("/")[-1])
    dao = JobDAO(dbsession)
    instances = await dao.get_job(jobid=jobid)
    assert instances is not None
    if instances is not None:
        assert instances.name == test_name


@pytest.mark.anyio
async def test_getting(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
    job_root_dir: Path,
    mock_current_api_token: str,
) -> None:
    """Tests job instance retrieval."""
    dao = JobDAO(dbsession)
    test_name = uuid.uuid4().hex
    application = "app1"
    job_id = await dao.create_job(name=test_name, application=application)
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(job_id))

    response = await client.get(url)
    jobs = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(jobs) == 4
    assert jobs["name"] == test_name
    assert jobs["id"] == job_id
    assert jobs["application"] == application
    assert jobs["state"] == "new"


@pytest.mark.anyio
async def test_upload(  # noqa: WPS218
    fastapi_app: FastAPI,
    client: AsyncClient,
    job_root_dir: Path,
    tmp_path: Path,
    mock_current_api_token: str,
) -> None:
    """Test upload of a job archive."""
    url = fastapi_app.url_path_for("upload_job", application="app1")
    archive_fn = tmp_path / "upload.zip"
    archive = ZipFile(archive_fn, mode="w")
    archive.writestr("job.ini", "# Example config file")
    archive.writestr("input.csv", "# Example input data file")
    archive.close()

    with open(archive_fn, "rb") as archive_file:
        files = {
            "upload": (
                "upload.zip",
                archive_file,
                "application/zip",
            ),
        }
        response = await client.put(url, files=files)

    job_id = response.headers["location"].split("/")[-1]
    assert response.status_code == status.HTTP_303_SEE_OTHER

    # poll for job status until ok, error or timeout
    jurl = fastapi_app.url_path_for("retrieve_job", jobid=job_id)
    job = None
    for _i in range(10):
        jresponse = await client.get(jurl)
        job = jresponse.json()
        if job["state"] in {"ok", "error"}:
            break
        await sleep(0.1)
    else:
        assert job is not None

    assert job["state"] == "ok"

    job_dir = job_root_dir / job_id
    meta_content = (job_dir / "meta").read_text()
    assert job_id in meta_content and mock_current_api_token in meta_content
    assert (job_dir / "job.ini").read_text() == "# Example config file"
    assert (job_dir / "input.csv").read_text() == "# Example input data file"
    assert (job_dir / "stdout.txt").read_text() == " 0  4 21 job.ini\n"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "returncode").read_text() == "0"
