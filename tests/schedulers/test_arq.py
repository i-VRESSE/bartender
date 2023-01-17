from pathlib import Path
from typing import Generator

import pytest
from arq.jobs import JobStatus
from pydantic import RedisDsn
from testcontainers.redis import RedisContainer

from bartender.db.models.job_model import State
from bartender.schedulers.arq import _map_arq_status  # noqa: WPS450
from bartender.schedulers.arq import ArqScheduler, ArqSchedulerConfig, arq_worker
from tests.schedulers.test_helpers import assert_output, prepare_input, wait_for_job


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
    with RedisContainer() as container:
        yield container


@pytest.fixture
def redis_dsn(redis_server: RedisContainer) -> str:
    host = redis_server.get_container_host_ip()
    port = redis_server.get_exposed_port(redis_server.port_to_expose)
    return f"redis://{host}:{port}"


@pytest.fixture
def arq_config_fixture(redis_dsn: RedisDsn) -> ArqSchedulerConfig:
    return ArqSchedulerConfig(redis_dsn=redis_dsn)


@pytest.fixture
def arq_worker_fixture(arq_config_fixture: ArqSchedulerConfig) -> None:
    return arq_worker(arq_config_fixture)


@pytest.mark.anyio
async def test_submit(arq_config_fixture: ArqSchedulerConfig, tmp_path: Path) -> None:
    job_dir = tmp_path
    description = prepare_input(job_dir)
    scheduler = ArqScheduler(arq_config_fixture)

    jid = await scheduler.submit(description)

    await wait_for_job(scheduler, jid)

    assert_output(job_dir)
