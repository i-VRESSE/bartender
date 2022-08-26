import uuid

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
    instances = await dao.filter(jobid=jobid)
    assert instances is not None
    if instances is not None:
        assert instances.name == test_name


@pytest.mark.anyio
async def test_getting(
    fastapi_app: FastAPI,
    client: AsyncClient,
    dbsession: AsyncSession,
) -> None:
    """Tests job instance retrieval."""
    dao = JobDAO(dbsession)
    test_name = uuid.uuid4().hex
    job_id = await dao.create_job(name=test_name)
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(job_id))
    response = await client.get(url)
    dummies = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert len(dummies) == 2
    assert dummies["name"] == test_name
    assert dummies["id"] == job_id
