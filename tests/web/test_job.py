import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fs.tarfs import TarFS
from fs.zipfs import ZipFS
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.config import Config, InteractiveApplicationConfiguration
from bartender.context import Context
from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import State
from bartender.destinations import Destination
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.queue import FileStagingQueue
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.user import User
from bartender.web.api.job.views import retrieve_job, retrieve_jobs

somedt = datetime(2022, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
async def mock_db_of_job(
    dbsession: AsyncSession,
    current_user: User,
) -> Optional[int]:
    """Fixture that inserts single new job into db."""
    # This mock is incomplete as it only does db stuff, it excludes staging of files
    dao = JobDAO(dbsession)
    return await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=current_user.username,
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

    job_subdir = job_dir / "output"
    job_subdir.mkdir()
    (job_subdir / "readme.txt").write_text("hi from output dir")
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
async def test_retrieve_jobs_given_notowner_of_any(
    fastapi_app: FastAPI,
    client: AsyncClient,
    mock_db_of_job: int,
    second_user_token: str,
) -> None:
    url = fastapi_app.url_path_for("retrieve_jobs")
    headers = {"Authorization": f"Bearer {second_user_token}"}
    response = await client.get(url, headers=headers)

    jobs = response.json()
    assert not len(jobs)


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
async def test_retrieve_job_given_notowner(
    fastapi_app: FastAPI,
    client: AsyncClient,
    mock_db_of_job: int,
    second_user_token: str,
) -> None:
    url = fastapi_app.url_path_for("retrieve_job", jobid=str(mock_db_of_job))
    headers = {"Authorization": f"Bearer {second_user_token}"}
    response = await client.get(url, headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Job not found"}


@pytest.mark.anyio
async def test_retrieve_job_new(
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


@pytest.mark.anyio
async def test_retrieve_job_queued2running(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    demo_context: Context,
) -> None:
    dao = JobDAO(dbsession)
    job_id, download_mock = await prepare_job(
        db_state="queued",
        scheduler_state="running",
        dao=dao,
        current_user=current_user,
        demo_context=demo_context,
    )

    job = await retrieve_job(
        job_id,
        dao,
        current_user,
        demo_context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job.state == "running"
    download_mock.assert_not_called()


@pytest.mark.anyio
async def test_retrieve_job_completed(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    demo_context: Context,
) -> None:
    dao = JobDAO(dbsession)
    job_id, download_mock = await prepare_job(
        db_state="ok",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        demo_context=demo_context,
    )

    job = await retrieve_job(
        job_id,
        dao,
        current_user,
        demo_context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job.state == "ok"
    download_mock.assert_not_called()


@pytest.mark.anyio
async def test_retrieve_job_running2ok(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    demo_context: Context,
) -> None:
    dao = JobDAO(dbsession)
    job_id, download_mock = await prepare_job(
        db_state="running",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        demo_context=demo_context,
    )

    job1 = await retrieve_job(
        job_id,
        dao,
        current_user,
        demo_context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job1.state == "staging_out"

    # wait for download task to complete
    await demo_file_staging_queue.join()

    job2 = await retrieve_job(
        job_id,
        dao,
        current_user,
        demo_context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert job2.state == "ok"

    download_mock.assert_called_once()


@pytest.mark.anyio
async def test_retrieve_jobs_queued2running(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    demo_context: Context,
) -> None:
    dao = JobDAO(dbsession)
    job_id, download_mock = await prepare_job(
        db_state="queued",
        scheduler_state="running",
        dao=dao,
        current_user=current_user,
        demo_context=demo_context,
    )

    jobs = await retrieve_jobs(
        job_dao=dao,
        user=current_user,
        context=demo_context,
        file_staging_queue=demo_file_staging_queue,
    )

    assert len(jobs) == 1
    assert jobs[0].id == job_id
    assert jobs[0].state == "running"

    download_mock.assert_not_called()


@pytest.mark.anyio
async def test_retrieve_jobs_running2staging_out(
    dbsession: AsyncSession,
    current_user: User,
    demo_file_staging_queue: FileStagingQueue,
    demo_context: Context,
) -> None:
    dao = JobDAO(dbsession)
    job_id, download_mock = await prepare_job(
        db_state="running",
        scheduler_state="ok",
        dao=dao,
        current_user=current_user,
        demo_context=demo_context,
    )

    jobs = await retrieve_jobs(
        job_dao=dao,
        user=current_user,
        context=demo_context,
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

    async def close(self) -> None:
        raise NotImplementedError()


async def prepare_job(
    db_state: State,
    scheduler_state: State,
    dao: JobDAO,
    current_user: User,
    demo_context: Context,
) -> tuple[int, Mock]:
    job_id = await dao.create_job(
        name="testjob1",
        application="app1",
        submitter=current_user.username,
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
    demo_context.destinations["dest1"] = destination
    return job_id, download_mock


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


@pytest.mark.anyio
async def test_directories(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    job_id = str(mock_ok_job)
    url = fastapi_app.url_path_for("retrieve_job_directories", jobid=job_id)
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    expected = {
        "name": "",
        "path": ".",
        "is_dir": True,
        "is_file": False,
        "children": [
            {
                "is_dir": True,
                "is_file": False,
                "name": "output",
                "path": "output",
            },
            {
                "is_dir": False,
                "is_file": True,
                "name": "somefile.txt",
                "path": "somefile.txt",
            },
            {
                "is_dir": False,
                "is_file": True,
                "name": "stderr.txt",
                "path": "stderr.txt",
            },
            {
                "is_dir": False,
                "is_file": True,
                "name": "stdout.txt",
                "path": "stdout.txt",
            },
        ],
    }
    assert response.json() == expected


@pytest.mark.anyio
async def test_directories_from_path(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
    job_root_dir: Path,
) -> None:
    job_id = str(mock_ok_job)
    job_dir = job_root_dir / str(job_id)
    dir1 = job_dir / "somedir"
    dir1.mkdir()
    (dir1 / "somefile1.txt").write_text("some text")

    url = fastapi_app.url_path_for(
        "retrieve_job_directories_from_path",
        jobid=job_id,
        path="somedir",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    expected = {
        "name": "somedir",
        "path": "somedir",
        "is_dir": True,
        "is_file": False,
        "children": [
            {
                "is_dir": False,
                "is_file": True,
                "name": "somefile1.txt",
                "path": "somedir/somefile1.txt",
            },
        ],
    }
    assert response.json() == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "archive_format",
    [".zip", ".tar", ".tar.xz", ".tar.gz", ".tar.bz2"],
)
async def test_job_directory_as_archive(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
    archive_format: str,
) -> None:
    url = (
        fastapi_app.url_path_for(
            "retrieve_job_directory_as_archive",
            jobid=mock_ok_job,
        )
        + f"?archive_format={archive_format}"
    )
    response = await client.get(url, headers=auth_headers)

    expected_content_type = (
        "application/zip" if archive_format == ".zip" else "application/x-tar"
    )
    expected_content_disposition = (
        f'attachment; filename="{mock_ok_job}{archive_format}"'
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == expected_content_type
    assert response.headers["content-disposition"] == expected_content_disposition

    fs = ZipFS if archive_format == ".zip" else TarFS

    with io.BytesIO(response.content) as responsefile:
        with fs(responsefile) as archive:
            stdout = archive.readtext("stdout.txt")

    assert stdout == "this is stdout"


@pytest.mark.anyio
async def test_job_subdirectory_as_archive(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    url = fastapi_app.url_path_for(
        "retrieve_job_subdirectory_as_archive",
        jobid=mock_ok_job,
        path="output",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/zip"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="output.zip"'
    )

    with io.BytesIO(response.content) as responsefile:
        with ZipFS(responsefile) as archive:
            stdout = archive.readtext("readme.txt")

    assert stdout == "hi from output dir"


@pytest.fixture
def demo_interactive_application(
    demo_config: Config,
) -> InteractiveApplicationConfiguration:
    config = InteractiveApplicationConfiguration(
        command_template="echo hello",
        input_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
        },
        timeout=10.0,
    )
    demo_config.interactive_applications["wcm"] = config
    return config


@pytest.mark.anyio
async def test_run_interactive_app_invalid_jobapp(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
    demo_config: Config,
) -> None:
    config = InteractiveApplicationConfiguration(
        command_template="echo hello",
        input_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
        },
        timeout=10.0,
        job_application="app2",  # mock_ok_job has app1
    )
    demo_config.interactive_applications["wcm"] = config
    job_id = str(mock_ok_job)

    url = fastapi_app.url_path_for(
        "run_interactive_app",
        jobid=job_id,
        application="wcm",
    )
    response = await client.post(url, headers=auth_headers)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json() == {"detail": 'Job was not run with application "app1"'}


@pytest.mark.anyio
async def test_run_interactive_app_invalid_requestbody(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
    demo_config: Config,
) -> None:
    config = InteractiveApplicationConfiguration(
        command_template="echo hello",
        input_schema={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
        },
        timeout=10.0,
        job_application="app1",  # mock_ok_job has app1
    )
    demo_config.interactive_applications["wcm"] = config
    job_id = str(mock_ok_job)

    url = fastapi_app.url_path_for(
        "run_interactive_app",
        jobid=job_id,
        application="wcm",
    )
    response = await client.post(url, headers=auth_headers, json={"foo": "bar"})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json() == {
        "detail": "Additional properties are not allowed ('foo' was unexpected)",
    }


@pytest.mark.anyio
async def test_rename_job_name(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    url = fastapi_app.url_path_for("rename_job_name", jobid=str(mock_ok_job))
    response = await client.post(url, headers=auth_headers, json="newname")

    assert response.status_code == status.HTTP_200_OK

    url = fastapi_app.url_path_for("retrieve_job", jobid=str(mock_ok_job))
    response2 = await client.get(url, headers=auth_headers)
    assert response2.status_code == status.HTTP_200_OK

    renamed_job = response2.json()
    assert renamed_job["name"] == "newname"


@pytest.mark.anyio
async def test_rename_job_name_too_short(
    fastapi_app: FastAPI,
    client: AsyncClient,
    auth_headers: Dict[str, str],
    mock_ok_job: int,
) -> None:
    jobid = str(mock_ok_job)
    name = ""
    url = fastapi_app.url_path_for("rename_job_name", jobid=jobid)
    response = await client.post(url, headers=auth_headers, json=name)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    expected = {
        "detail": [
            {
                "ctx": {"limit_value": 1},
                "loc": ["body"],
                "msg": "ensure this value has at least 1 characters",
                "type": "value_error.any_str.min_length",
            },
        ],
    }
    assert response.json() == expected


@pytest.mark.anyio
async def test_rename_job_name_wrong_user(
    fastapi_app: FastAPI,
    client: AsyncClient,
    second_user_token: str,
    mock_ok_job: int,
) -> None:
    jobid = str(mock_ok_job)
    name = "newname"
    url = fastapi_app.url_path_for("rename_job_name", jobid=jobid)
    headers = {"Authorization": f"Bearer {second_user_token}"}
    response = await client.post(url, headers=headers, json=name)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Job not found"}
