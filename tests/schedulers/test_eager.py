from pathlib import Path

import pytest

from bartender.schedulers.abstract import JobDescription, JobSubmissionError
from bartender.schedulers.eager import EagerScheduler, EagerSchedulerConfig


@pytest.mark.anyio
async def test_ok_running_job(tmp_path: Path) -> None:
    async with EagerScheduler(EagerSchedulerConfig()) as scheduler:
        description = JobDescription(command="echo -n hello", job_dir=tmp_path)

        jid = await scheduler.submit(description)

        assert (await scheduler.state(jid)) == "ok"
        assert (tmp_path / "returncode").read_text() == "0"
        assert (tmp_path / "stdout.txt").read_text() == "hello"


@pytest.mark.anyio
async def test_bad_running_job(tmp_path: Path) -> None:
    async with EagerScheduler(EagerSchedulerConfig()) as scheduler:
        description = JobDescription(command="exit 42", job_dir=tmp_path)

        with pytest.raises(JobSubmissionError, match="Job failed with return code 42"):
            await scheduler.submit(description)
