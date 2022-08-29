import uuid
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.db.dao.job_dao import JobDAO


@pytest.mark.anyio
async def test_getting_all(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
    job_root_dir: Path,
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
) -> None:
    """Tests job instance retrieval."""
    dao = JobDAO(dbsession)
    test_name = uuid.uuid4().hex
    job_id = await dao.create_job(name=test_name)
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(job_id))

    response = await client.get(url)
    jobs = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(jobs) == 2
    assert jobs["name"] == test_name
    assert jobs["id"] == job_id


@pytest.mark.anyio
async def test_upload(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
    job_root_dir: Path,
    tmp_path: Path,
) -> None:
    """Test upload of a job archive."""
    url = fastapi_app.url_path_for("upload_job", application="haddock3")
    archive_fn = tmp_path / "upload.zip"
    archive = ZipFile(archive_fn, mode="w")
    archive.writestr("workflow.cfg", "# Example config file")
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
    archive.close()

    job_id = response.headers["location"].split("/")[-1]
    assert response.status_code == status.HTTP_303_SEE_OTHER

    job_dir = job_root_dir / job_id
    assert job_dir.exists()
    assert (job_dir / "id").read_text() == job_id
    # TODO perform better comparison
    assert (job_dir / "archive.zip").stat().st_size == archive_fn.stat().st_size
