from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.user import User

somedt = datetime(2022, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
async def mock_db_of_job(
    dbsession: AsyncSession,
    current_user_token: str,
) -> Optional[int]:
    """Fixture that inserts single new job into db."""
    # This mock is incomplete as it only does db stuff, it excludes staging of files
    result = await dbsession.execute(select(User))
    user = result.unique().scalar_one()
    dao = JobDAO(dbsession)
    return await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=user,
        created_on=somedt,
        updated_on=somedt,
    )


@pytest.fixture
async def mock_ok_job(
    dbsession: AsyncSession,
    mock_db_of_job: int,
    job_root_dir: Path,
) -> int:
    job_id = mock_db_of_job
    dao = JobDAO(dbsession)
    await dao.update_internal_job_id(job_id, "internal-job-id", "dest1")
    await dao.update_job_state(job_id, "ok")
    job_dir = job_root_dir / str(job_id)
    job_dir.mkdir()
    (job_dir / "somefile.txt").write_text("hello")
    (job_dir / "stderr.txt").write_text("this is stderr")
    (job_dir / "stdout.txt").write_text("this is stdout")
    return job_id


@pytest.mark.anyio
async def test_retrieve_jobs_none(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    retrieve_url = fastapi_app.url_path_for("retrieve_jobs")
    response = await client.get(retrieve_url, headers=auth_headers)
    jobs = response.json()
    assert not len(jobs)


@pytest.mark.anyio
async def test_retrieve_jobs_one(
    fastapi_app: FastAPI,
    client: AsyncClient,
    mock_db_of_job: int,
    auth_headers: Dict[str, str],
) -> None:
    retrieve_url = fastapi_app.url_path_for("retrieve_jobs")
    response = await client.get(retrieve_url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    jobs = response.json()
    expected = [
        {
            "id": mock_db_of_job,
            "name": "testjob1",
            "application": "app1",
            "state": "new",
            "created_on": somedt.isoformat(),
            "updated_on": somedt.isoformat(),
        },
    ]
    assert jobs == expected


@pytest.mark.anyio
async def test_retrieve_job_badid(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Tests job instance retrieval."""
    url = fastapi_app.url_path_for("retrieve_job", jobid="999999")
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Job not found"}


@pytest.mark.anyio
async def test_retrieve_job(
    fastapi_app: FastAPI,
    client: AsyncClient,
    mock_db_of_job: int,
    auth_headers: Dict[str, str],
) -> None:
    """Tests job instance retrieval."""
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(mock_db_of_job))
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    job = response.json()
    expected = {
        "id": mock_db_of_job,
        "name": "testjob1",
        "application": "app1",
        "state": "new",
        "created_on": somedt.isoformat(),
        "updated_on": somedt.isoformat(),
    }
    assert job == expected


@pytest.mark.anyio
async def test_files_of_noncomplete_job(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_db_of_job: int,
) -> None:
    # mock_db_of_job has state==new
    url = fastapi_app.url_path_for(
        "retrieve_job_files",
        jobid=str(mock_db_of_job),
        path="README.md",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_425_TOO_EARLY
    assert response.json() == {"detail": "Job has not completed"}


@pytest.mark.anyio
async def test_files_of_completed_job(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    path = "somefile.txt"
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_files", jobid=job_id, path=path)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == "hello"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == 'inline; filename="somefile.txt"'


@pytest.mark.anyio
async def test_files_given_path_is_dir(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    path = ""
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_files", jobid=job_id, path=path)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "File not found"}


@pytest.mark.parametrize(
    "test_input",
    [
        "/etc/passwd",
        "~/.ssh/id_rsa",
        # Job dir is <pytest_tmp_path>/jobs/6
        # to .. up to /etc/passwd use
        # escape / with %2F as un-escaped will
        # use resolve to URL that does not exist.
        "..%2F..%2F..%2F..%2F..%2F..%2Fetc%2Fpasswd",  # noqa: WPS323
    ],
)
@pytest.mark.anyio
async def test_files_given_bad_paths(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
    test_input: str,
) -> None:
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_files", jobid=job_id, path=test_input)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "File not found"}


@pytest.mark.anyio
async def test_stdout(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_stdout", jobid=job_id)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == "this is stdout"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == 'inline; filename="stdout.txt"'


@pytest.mark.anyio
async def test_stderr(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_stderr", jobid=job_id)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.text == "this is stderr"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.headers["content-disposition"] == 'inline; filename="stderr.txt"'
