from asyncio import create_subprocess_shell, wait_for
from asyncio.subprocess import Process
from pathlib import Path
from typing import Literal
from uuid import uuid1

from pydantic import BaseModel, PositiveInt
from pydantic.types import PositiveFloat

from bartender.check_load import check_load
from bartender.db.models.job_model import State
from bartender.schedulers.abstract import (
    AbstractScheduler,
    JobDescription,
    JobSubmissionError,
)


class EagerSchedulerConfig(BaseModel):
    """Configuration for eager scheduler.

    Args:
        max_load: Maximum load that scheduler will process submissions.
        timeout: Maximum time to wait for job to finish. In seconds.

    """

    type: Literal["eager"] = "eager"
    max_load: PositiveFloat = 1.0
    timeout: PositiveInt = 300


async def _exec(description: JobDescription, timeout: int) -> None:
    stderr_fn = description.job_dir / "stderr.txt"
    stdout_fn = description.job_dir / "stdout.txt"

    with open(stderr_fn, "w") as stderr:
        with open(stdout_fn, "w") as stdout:
            proc = await create_subprocess_shell(
                description.command,
                stdout=stdout,
                stderr=stderr,
                cwd=description.job_dir,
            )
            try:
                await _handle_job_completion(timeout, proc, description.job_dir)
            except TimeoutError:
                raise JobSubmissionError(f"Job took longer than {timeout} seconds")


async def _handle_job_completion(timeout: int, proc: Process, job_dir: Path) -> None:
    returncode = await wait_for(proc.wait(), timeout=timeout)
    (job_dir / "returncode").write_text(str(returncode))
    if returncode != 0:
        raise JobSubmissionError(
            f"Job failed with return code {returncode}",
        )


class EagerScheduler(AbstractScheduler):
    """Scheduler that runs jobs immediately on submission."""

    def __init__(self, config: EagerSchedulerConfig) -> None:
        self.config = config

    async def submit(self, description: JobDescription) -> str:  # noqa: D102
        check_load(self.config.max_load)
        await _exec(description, self.config.timeout)
        return str(uuid1())

    async def state(self, job_id: str) -> State:  # noqa: D102
        return "ok"

    async def states(self, job_ids: list[str]) -> list[State]:  # noqa: D102
        return ["ok" for _ in job_ids]

    async def cancel(self, job_id: str) -> None:  # noqa: D102
        pass  # noqa: WPS420 -- cannot cancel job that is already completed.

    async def close(self) -> None:  # noqa: D102
        pass  # noqa: WPS420 -- nothing to close.
