import time
from asyncio import sleep
from pathlib import Path

import DIRAC
import pytest
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import (
    JobMonitoringClient,
)
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient

from bartender.db.models.job_model import CompletedStates, State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.dirac import DiracScheduler

# TODO do not have copy of testers.helpers methods


def prepare_input(job_dir: Path) -> JobDescription:
    (job_dir / "input").write_text("Lorem ipsum")
    return JobDescription(
        command="echo -n hello && wc input > output",
        job_dir=job_dir,
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


def test_submit():
    DIRAC.initialize()
    wms_client = WMSClient()
    monitoring = JobMonitoringClient()
    jdl = """\
    JobName = "Simple_Job";
    Executable = "/bin/ls";
    Arguments = "-ltr";
    StdOutput = "StdOut";
    StdError = "StdErr";
    OutputSandbox = {"StdOut","StdErr"};
    """
    res = wms_client.submitJob(jdl)
    job_id = res["Value"]
    print(f"Job submitted with id {job_id}")
    max_checks = 100
    sleep_time = 3
    for i in range(max_checks):
        print("Checking status")
        result = monitoring.getJobsStatus(job_id)
        if result["Value"][job_id]["Status"] == "Done":
            break
        time.sleep(sleep_time)
    else:
        raise Exception("Failed to finish job")


@pytest.mark.anyio
async def test_it(tmp_path: Path):
    scheduler = DiracScheduler()
    description = prepare_input(tmp_path)
    jid = await scheduler.submit(description)

    await wait_for_job(scheduler, jid)
