from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.config import ApplicatonConfiguration
from bartender.context import Context
from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import State
from bartender.db.models.user import User
from bartender.destinations import Destination
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.queue import FileStagingQueue
from bartender.picker import pick_first
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.web.api.job.views import retrieve_job, retrieve_jobs

somedt = datetime(2022, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
async def mock_db_job(
    dbsession: AsyncSession,
    current_user: User,
) -> Optional[int]:
    """Fixture that inserts single new job into db."""
    # This mock is incomplete as it only does db stuff, it excludes staging of files
    dao = JobDAO(dbsession)
    return await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=current_user,
        created_on=somedt,
        updated_on=somedt,
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
            "created_on": somedt.isoformat(),
            "updated_on": somedt.isoformat(),
        },
    ]
    assert jobs == expected


@pytest.mark.anyio
async def test_retrieve_job_new(
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
        "created_on": somedt.isoformat(),
        "updated_on": somedt.isoformat(),
    }
    assert job == expected


async def test_retrieve_job_unknown(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    url = fastapi_app.url_path_for("retrieve_job", jobid="999999")
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_retrieve_job_stdout_unknown(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    url = fastapi_app.url_path_for("retrieve_job_stdout", jobid="999999")
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_retrieve_job_queued2running(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dao = JobDAO(dbsession)
    job_id, context, download_mock = await prepare_job(
        db_state="queued",
        scheduler_state="running",
        dao=dao,
        current_user=current_user,
        job_root_dir=job_root_dir,
        demo_applications=demo_applications,
    )

    job = await retrieve_job(
        job_id,
        dao,
        current_user,
        context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job.state == "running"
    download_mock.assert_not_called()


async def test_retrieve_job_completed(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dao = JobDAO(dbsession)
    job_id, context, download_mock = await prepare_job(
        db_state="ok",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        job_root_dir=job_root_dir,
        demo_applications=demo_applications,
    )

    job = await retrieve_job(
        job_id,
        dao,
        current_user,
        context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job.state == "ok"
    download_mock.assert_not_called()


async def test_retrieve_job_running2ok(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dao = JobDAO(dbsession)
    job_id, context, download_mock = await prepare_job(
        db_state="running",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        job_root_dir=job_root_dir,
        demo_applications=demo_applications,
    )

    job1 = await retrieve_job(
        job_id,
        dao,
        current_user,
        context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job1.state == "staging_out"

    # wait for download task to complete
    await demo_file_staging_queue.join()

    job2 = await retrieve_job(
        job_id,
        dao,
        current_user,
        context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job2.state == "ok"

    download_mock.assert_called_once()


async def test_retrieve_jobs_queued2running(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dao = JobDAO(dbsession)
    job_id, context, download_mock = await prepare_job(
        db_state="queued",
        scheduler_state="running",
        dao=dao,
        current_user=current_user,
        job_root_dir=job_root_dir,
        demo_applications=demo_applications,
    )

    jobs = await retrieve_jobs(
        job_dao=dao,
        user=current_user,
        context=context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert len(jobs) == 1
    assert jobs[0].id == job_id
    assert jobs[0].state == "running"

    download_mock.assert_not_called()


async def test_retrieve_jobs_running2staging_out(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dao = JobDAO(dbsession)
    job_id, context, download_mock = await prepare_job(
        db_state="running",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        job_root_dir=job_root_dir,
        demo_applications=demo_applications,
    )

    jobs = await retrieve_jobs(
        job_dao=dao,
        user=current_user,
        context=context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert len(jobs) == 1
    assert jobs[0].id == job_id
    assert jobs[0].state == "staging_out"

    # wait for download task to complete
    await demo_file_staging_queue.join()

    download_mock.assert_called_once()


class FakeScheduler(AbstractScheduler):
    def __init__(self, scheduler_state: State) -> None:
        self.scheduler_state = scheduler_state

    async def state(self, job_id: str) -> State:
        return self.scheduler_state

    async def states(self, job_ids: list[str]) -> list[State]:
        return [self.scheduler_state]

    async def submit(self, description: JobDescription) -> str:
        raise NotImplementedError()

    async def cancel(self, job_id: str) -> None:
        raise NotImplementedError()

    async def close(self) -> None:
        raise NotImplementedError()


class FakeFileSystem(AbstractFileSystem):
    def __init__(self, download_mock: Mock) -> None:
        self.download_mock = download_mock

    def localize_description(
        self,
        description: JobDescription,
        entry: Path,
    ) -> JobDescription:
        return description

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        self.download_mock(src, target)

    async def upload(self, src: JobDescription, target: JobDescription) -> None:
        raise NotImplementedError()

    def close(self) -> None:
        raise NotImplementedError()


async def prepare_job(
    db_state: State,
    scheduler_state: State,
    dao: JobDAO,
    current_user: User,
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> tuple[int, Context, Mock]:
    job_id = await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=current_user,
        created_on=somedt,
        updated_on=somedt,
    )
    if job_id is None:
        raise NotImplementedError()
    await dao.update_internal_job_id(job_id, "fake-internal-job-id", "dest1")
    await dao.update_job_state(job_id, db_state)

    download_mock = Mock()

    destination = Destination(
        scheduler=FakeScheduler(scheduler_state),
        filesystem=FakeFileSystem(download_mock),
    )
    context = Context(
        destination_picker=pick_first,
        job_root_dir=job_root_dir,
        applications=demo_applications,
        destinations={"dest1": destination},
    )
    return job_id, context, download_mock
