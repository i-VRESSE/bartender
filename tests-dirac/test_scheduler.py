from asyncio import sleep
from pathlib import Path

import pytest

from bartender.db.models.job_model import CompletedStates, State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.dirac import DiracScheduler

# TODO do not have copy of testers.helpers methods


def prepare_input(job_dir: Path) -> JobDescription:
    (job_dir / "input").write_text("Lorem ipsum")
    return JobDescription(
        command="echo -n hello && wc input > output/output.txt",
        job_dir=job_dir,
    )


def assert_output(job_dir: Path) -> None:
    assert (job_dir / "returncode").read_text() == "0"
    assert (job_dir / "stdout.txt").read_text() == "hello"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "input").exists()
    assert (job_dir / "output" / "output.txt").read_text().strip() == "0  2 11 input"


async def wait_for_job(
    scheduler: AbstractScheduler,
    job_id: str,
    expected: State = "ok",
    delay: float = 0.5,
    attempts: int = 30,
) -> None:
    for _ in range(attempts):
        state = await scheduler.state(job_id)
        if state in CompletedStates:
            break
        await sleep(delay)

    assert state == expected


@pytest.mark.anyio
async def test_it(tmp_path: Path):
    scheduler = DiracScheduler()
    description = prepare_input(tmp_path)
    jid = await scheduler.submit(description)

    await wait_for_job(scheduler, jid)
