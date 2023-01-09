from asyncio import sleep
from pathlib import Path

import pytest

from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.memory import (
    KILLED_RETURN_CODE,
    MemoryScheduler,
    MemorySchedulerConfig,
)


@pytest.mark.anyio
async def test_ok_running_job(tmp_path: Path) -> None:
    try:
        scheduler = MemoryScheduler(MemorySchedulerConfig(slots=1))
        description = JobDescription(command="echo -n hello", job_dir=str(tmp_path))

        jid = await scheduler.submit(description)

        # Wait for job to complete
        await sleep(0.01)
        assert (await scheduler.state(jid)) == "ok"
        assert (tmp_path / "returncode").read_text() == "0"
        assert (tmp_path / "stdout.txt").read_text() == "hello"
    finally:
        await scheduler.close()


@pytest.mark.anyio
async def test_bad_running_job(tmp_path: Path) -> None:
    try:
        scheduler = MemoryScheduler(MemorySchedulerConfig(slots=1))
        description = JobDescription(command="exit 42", job_dir=str(tmp_path))

        jid = await scheduler.submit(description)

        # Wait for job to complete
        await sleep(0.01)
        assert (await scheduler.state(jid)) == "error"
        assert (tmp_path / "returncode").read_text() == "42"
    finally:
        await scheduler.close()


@pytest.mark.anyio
async def test_cancel_running_job(tmp_path: Path) -> None:
    try:
        scheduler, jid, _ = await make_occupied_scheduler(tmp_path)

        await scheduler.cancel(jid)

        # Wait for job to be cancelled
        await sleep(0.01)
        assert (await scheduler.state(jid)) == "error"
        assert (tmp_path / "returncode").read_text() == KILLED_RETURN_CODE
    finally:
        await scheduler.close()


async def make_occupied_scheduler(
    tmp_path: Path,
) -> tuple[MemoryScheduler, str, JobDescription]:
    scheduler = MemoryScheduler(MemorySchedulerConfig(slots=1))
    description = JobDescription(command="sleep 5", job_dir=str(tmp_path))
    jid = await scheduler.submit(description)
    # Wait for job to start running
    await sleep(0.01)
    assert (await scheduler.state(jid)) == "running"
    return scheduler, jid, description


@pytest.mark.anyio
async def test_cancel_queud_job(tmp_path: Path) -> None:
    try:
        scheduler, _, description = await make_occupied_scheduler(tmp_path)

        # All slots are occupied, so next submit will be queued
        jid2 = await scheduler.submit(description)

        await scheduler.cancel(jid2)

        with pytest.raises(KeyError):
            await scheduler.state(jid2)
    finally:
        await scheduler.close()
