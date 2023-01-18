from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
from arq import Worker
from arq.jobs import JobStatus
from pydantic import RedisDsn
from testcontainers.redis import RedisContainer

from bartender.db.models.job_model import State
from bartender.schedulers.arq import _map_arq_status  # noqa: WPS450
from bartender.schedulers.arq import ArqScheduler, ArqSchedulerConfig, arq_worker
from tests.schedulers.helpers import assert_output, prepare_input


@pytest.mark.parametrize(
    "arq_status,success,expected",
    [
        (JobStatus.deferred, False, "queued"),
        (JobStatus.queued, False, "queued"),
        (JobStatus.in_progress, False, "running"),
        (JobStatus.complete, True, "ok"),
        (JobStatus.complete, False, "error"),
        (JobStatus.not_found, False, "error"),
    ],
)
def test_map_arq_status(arq_status: JobStatus, success: bool, expected: State) -> None:
    assert _map_arq_status(arq_status, success) == expected


@pytest.fixture
def redis_server() -> Generator[RedisContainer, None, None]:
    with RedisContainer("redis:7") as container:
        yield container


@pytest.fixture
def redis_dsn(redis_server: RedisContainer) -> str:
    host = redis_server.get_container_host_ip()
    port = redis_server.get_exposed_port(redis_server.port_to_expose)
    return f"redis://{host}:{port}/0"


@pytest.fixture
def config(redis_dsn: RedisDsn) -> ArqSchedulerConfig:
    return ArqSchedulerConfig(redis_dsn=redis_dsn)


@pytest.fixture
async def worker(
    config: ArqSchedulerConfig,
) -> AsyncGenerator[Worker, None]:
    # Use burst so worker.main() stops once all jobs have been run
    myworker = arq_worker(config, burst=True)
    yield myworker
    await myworker.close()


@pytest.fixture
async def scheduler(config: ArqSchedulerConfig) -> AsyncGenerator[ArqScheduler, None]:
    myscheduler = ArqScheduler(config)
    yield myscheduler
    await myscheduler.close()


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.anyio
async def test_state_for_unknown_job_id(scheduler: ArqScheduler) -> None:
    with pytest.raises(KeyError):
        await scheduler.state("unknownjobid")


def test_eq_good(scheduler: ArqScheduler, redis_dsn: RedisDsn) -> None:
    same = ArqScheduler(ArqSchedulerConfig(redis_dsn=redis_dsn))
    assert scheduler == same


def test_eq_diff_class(scheduler: ArqScheduler) -> None:
    diff = "somethingelse"
    assert scheduler != diff


def test_eq_diff_config(scheduler: ArqScheduler) -> None:
    diff = ArqScheduler(
        ArqSchedulerConfig(redis_dsn="redis://somehost", queue="somequeue"),
    )
    assert scheduler != diff


@pytest.mark.anyio
async def test_repr(scheduler: ArqScheduler, redis_dsn: RedisDsn) -> None:
    redis = f"redis_dsn=RedisDsn('{redis_dsn}'"
    config = f"ArqSchedulerConfig(type='arq', {redis}, ), queue='arq:queue')"
    expected = f"ArqScheduler(config={config})"
    assert repr(scheduler) == expected


@pytest.fixture
async def submitted_job_id(scheduler: ArqScheduler, job_dir: Path) -> str:
    description = prepare_input(job_dir)
    return await scheduler.submit(description)


@pytest.mark.anyio
async def test_submitted_job_has_queued_state(
    scheduler: ArqScheduler,
    submitted_job_id: str,
) -> None:
    state = await scheduler.state(submitted_job_id)
    assert state == "queued"


@pytest.fixture
async def completed_job_id(submitted_job_id: str, worker: Worker) -> str:
    await worker.main()
    return submitted_job_id


class TestCompletedJob:
    @pytest.mark.anyio
    async def test_has_ok_state(
        self,
        scheduler: ArqScheduler,
        completed_job_id: str,
    ) -> None:
        state = await scheduler.state(completed_job_id)
        assert state == "ok"

    def test_has_output(self, completed_job_id: str, job_dir: Path) -> None:
        assert_output(job_dir)


@pytest.mark.anyio
async def test_cancelling_queued_job(
    scheduler: ArqScheduler,
    tmp_path: Path,
    config: ArqSchedulerConfig,
) -> None:
    job_dir = tmp_path
    description = prepare_input(job_dir)
    submitted_job_id = await scheduler.submit(description)
    queued_state = await scheduler.state(submitted_job_id)
    assert queued_state == "queued"

    await scheduler.cancel(submitted_job_id)

    # Run worker as it does aborting
    worker = arq_worker(config, burst=True)
    await worker.main()

    state = await scheduler.state(submitted_job_id)
    assert state == "error"
