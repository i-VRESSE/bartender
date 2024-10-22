from asyncio import sleep
from pathlib import Path

from bartender.db.models.job_model import CompletedStates, State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription


def prepare_input(job_dir: Path) -> JobDescription:
    (job_dir / "input").write_text("Lorem ipsum")
    return JobDescription(
        command="echo -n hello && wc input > output",
        job_dir=job_dir,
        submitter="testsubmitter",
        application="hellowc",
    )


def assert_output(job_dir: Path) -> None:
    assert (job_dir / "returncode").read_text() == "0"
    assert (job_dir / "stdout.txt").read_text() == "hello"
    assert (job_dir / "stderr.txt").read_text() == ""
    assert (job_dir / "input").exists()
    assert (job_dir / "output").read_text().strip() == "0  2 11 input"


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
