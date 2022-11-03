from typing import Dict, Optional

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.user import User


@pytest.fixture
async def mock_db_job(
    dbsession: AsyncSession,
    current_user_token: str,
) -> Optional[int]:
    # Mock is incomplete as it only does db stuff, it excludes staging of files
    result = await dbsession.execute(select(User))
    user = result.unique().scalar_one()
    dao = JobDAO(dbsession)
    return await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=user,
    )


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
    mock_db_job: int,
    auth_headers: Dict[str, str],
) -> None:
    retrieve_url = fastapi_app.url_path_for("retrieve_jobs")
    response = await client.get(retrieve_url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    jobs = response.json()
    expected = [
        {
            "id": mock_db_job,
            "name": "testjob1",
            "application": "app1",
            "state": "new",
        },
    ]
    dateless_jobs = [
        {key: job[key] for key in job if key not in {"created_on", "updated_on"}}
        for job in jobs
    ]
    assert dateless_jobs == expected


@pytest.mark.anyio
async def test_retrieve_job(
    fastapi_app: FastAPI,
    client: AsyncClient,
    mock_db_job: int,
    auth_headers: Dict[str, str],
) -> None:
    """Tests job instance retrieval."""
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(mock_db_job))
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    job = response.json()
    expected = {
        "id": mock_db_job,
        "name": "testjob1",
        "application": "app1",
        "state": "new",
    }
    dateless_job = {
        key: job[key] for key in job if key not in {"created_on", "updated_on"}
    }
    assert dateless_job == expected
