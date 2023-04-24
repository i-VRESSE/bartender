from pathlib import Path
from textwrap import dedent
from typing import Literal, Optional

import aiofiles
from DIRAC import gLogger, initialize
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import (
    JobMonitoringClient,
)
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient
from pydantic import BaseModel

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription

dirac_status_map: dict[str, State] = {
    "Waiting": "queued",
    "Staging": "queued",
    "Done": "ok",
    "Failed": "error",
    # TODO add all possible dirac job states
}

# TODO make proper async with loop.run_in_executor
# TODO test against Dirac in testcontainer and/or against live?


class DiracSchedulerConfig(BaseModel):
    type: Literal["dirac"] = "dirac"
    apptainer_image: Optional[Path] = None
    """Path on cvmfs to apptainer image wrap each job command in."""


class DiracScheduler(AbstractScheduler):
    """DIRAC scheduler.

    [More info](http://diracgrid.org/).
    """

    def __init__(self, config: DiracSchedulerConfig) -> None:
        """Constructor.

        Args:
            config: The config.
        """
        self.config: DiracSchedulerConfig = config
        # TODO make sure initialize is only called once per process
        initialize()
        gLogger.setLevel("debug")  # TODO remove
        # TODO use single client Dirac client instead of multiple clients.
        # See https://dirac.readthedocs.io/en/latest/CodeDocumentation/Interfaces/API/Dirac.html  # noqa: E501
        self.wms_client = WMSClient()
        self.monitoring = JobMonitoringClient()

    async def submit(self, description: JobDescription) -> str:
        """Submit a job description for running.

        Args:
            description: Description for a job.

        Raises:
            RuntimeError: When submission fails.

        Returns:
            Identifier that can be used later to interact with job.
        """
        jdl = await self._jdl_script(description)
        # TODO ship application to where it is run
        # TODO get output files of job in grid storage
        # TODO when input sandbox is to big then upload to grid storage
        result = self.wms_client.submitJob(jdl)
        if not result["OK"]:
            raise RuntimeError(result["Message"])
        return result["Value"]

    async def state(self, job_id: str) -> State:
        """Get state of a job.

        Once job is completed, then scheduler can forget job.

        Args:
            job_id: Identifier of job.

        Raises:
            RuntimeError: When getting job status fails.

        Returns:
            State of job.
        """
        # Dirac has Status,MinorStatus,ApplicationStatus
        # TODO Should we also store MinorStatus,ApplicationStatus?
        result = self.monitoring.getJobsStatus(job_id)
        if not result["OK"]:
            raise RuntimeError(result["Message"])
        dirac_status = result["Value"][job_id]["Status"]
        return dirac_status_map[dirac_status]

    async def states(self, job_ids: list[str]) -> list[State]:
        """Get state of jobs.

        Once a job is completed, then scheduler can forget job.

        Args:
            job_ids: Identifiers of jobs.

        Raises:
            RuntimeError: When getting jobs status fails.

        Returns:
            States of jobs.
        """
        result = self.monitoring.getJobsStatus(job_ids)
        if not result["OK"]:
            raise RuntimeError(result["Message"])

        # TODO result can be in different order then job_ids
        return [dirac_status_map[value["Status"]] for value in result["Value"]]

    async def cancel(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Once a queued job is cancelled, then the scheduler can forget job.

        Args:
            job_id: Identifier of job.

        Raises:
            RuntimeError: When cancelling of job fails.
        """
        state = await self.state(job_id)
        if state == "running":
            result = self.wms_client.killJob(job_id)
        else:
            result = self.wms_client.deleteJob(job_id)
            # TODO or removeJob()?
        if not result["OK"]:
            raise RuntimeError(result["Message"])

    async def close(self) -> None:
        """Close scheduler."""

    async def _job_script(self, description: JobDescription) -> Path:
        file = Path(description.job_dir / "job.sh")
        command = description.command
        if self.config.apptainer_image:
            command = (
                f"apptainer run {self.config.apptainer_image} {description.command}"
            )
        async with aiofiles.open(file, "w") as f:
            await f.write(
                dedent(
                    f"""\
                    #!/bin/bash
                    set -e
                    # TODO download big input files
                    {command}
                    # TODO upload big output files
                    """,
                ),
            )
        return file

    async def _jdl_script(self, description: JobDescription) -> Path:
        jobsh = await self._job_script(description)

        files_in_job_dir = description.job_dir.rglob("*")
        exclude_from_sandbox = {description.job_dir / "job.jdl"}
        job_input_files = [
            f'"{file.absolute()}"'
            for file in files_in_job_dir
            if file not in exclude_from_sandbox
        ]
        # TODO exclude files to big for input sandbox
        input_sandbox = ",".join(job_input_files)

        file = Path(description.job_dir / "job.jdl")
        async with aiofiles.open(file, "w") as f:
            await f.write(
                dedent(
                    f"""\
                    JobName = "{description.job_dir.name}";
                    Executable = "{jobsh.absolute()}";
                    InputSandBox = {{{input_sandbox}}};
                    StdOutput = "stdout.txt";
                    StdError = "stderr.txt";
                    OutputSandbox = {{"stdout.txt","stderr.txt"}};
                    """,
                ),
            )
        return file
