import asyncio
from functools import partial, wraps
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
    "Received": "queued",
    "Waiting": "queued",
    "Staging": "queued",
    "Done": "ok",
    "Failed": "error",
    # TODO add all possible dirac job states
}


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


class DiracSchedulerConfig(BaseModel):
    type: Literal["dirac"] = "dirac"
    apptainer_image: Optional[Path] = None
    """Path on cvmfs to apptainer image wrap each job command in."""
    # TODO get vo from proxy
    # TODO remove defaults
    lfn_root: str = "/tutoVO/user/c/ciuser/bartenderjobs"
    output_se: str = "StorageElementOne"
    output_dir: str = "output"


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

        async_submit = async_wrap(self.wms_client.submitJob)
        result = await async_submit(jdl)
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
        async_state = async_wrap(self.monitoring.getJobsStatus)
        result = await async_state(job_id)
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
        async_state = async_wrap(self.monitoring.getJobsStatus)
        result = await async_state(job_ids)
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
            async_kill = async_wrap(self.wms_client.killJob)
            result = await async_kill(job_id)
        else:
            async_delete = async_wrap(self.wms_client.deleteJob)
            result = await async_delete(job_id)
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
        # default OutputSandboxLimit is 10Mb which is too small sometimes,
        # so always upload output dir to grid storage
        job_name = external_id_from_job_dir(description.job_dir)
        lfn_output_dir = external_id_to_lfn_output_dir(job_name, self.config)
        # fc = FileCatalogClient()
        # async_mkdir = async_wrap(fc.createDirectory)
        # TODO also upload any output files outside self.config.output_dir to grid storage
        # await async_mkdir(lfn_output_dir)
        async with aiofiles.open(file, "w") as f:
            await f.write(
                dedent(
                    f"""\
                    #!/bin/bash
                    set -e
                    {command}
                    # upload output files
                    # if [ -d "{self.config.output_dir}" ]; then
                    #     dirac-dms-directory-sync {self.config.output_dir} {lfn_output_dir} {self.config.output_se}
                    # fi
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
        # Dirac code
        # https://github.com/DIRACGrid/DIRAC/blob/7abf70debfefa8135aeff439a3296f392ab8342b/src/DIRAC/WorkloadManagementSystem/Client/WMSClient.py#L135
        # does not have a size limit for the InputSandbox
        # so upload all files found in job_dir to InputSandbox
        input_sandbox = ",".join(job_input_files)

        file = Path(description.job_dir / "job.jdl")
        job_name = external_id_from_job_dir(description.job_dir)
        lfn_output_path = external_id_to_lfn_output_path(job_name, self.config)
        async with aiofiles.open(file, "w") as f:
            await f.write(
                dedent(
                    f"""\
                    JobName = "{job_name}";
                    Executable = "{jobsh.name}";
                    InputSandbox = {{{input_sandbox}}};
                    StdOutput = "stdout.txt";
                    StdError = "stderr.txt";
                    OutputSandbox = {{"stdout.txt","stderr.txt"}};
                    OutputPath = {{"{lfn_output_path}"}};
                    OutputSE = {{"{self.config.output_se}"}};
                    # ** flattens dirs, so ./output/output.txt is uploaded as ./output.txt
                    # cannot use
                    OutputData = {{"**"}};
                    """,
                ),
            )
        return file


def external_id_from_job_dir(job_dir: Path) -> str:
    return job_dir.name


def external_id_to_lfn_output_path(
    external_job_id: str,
    config: DiracSchedulerConfig,
) -> str:
    return f"{config.lfn_root}/{external_job_id}"


def external_id_to_lfn_output_dir(
    external_job_id: str,
    config: DiracSchedulerConfig,
) -> str:
    path = external_id_to_lfn_output_path(external_job_id, config)
    return f"{path}/{config.output_dir}"
