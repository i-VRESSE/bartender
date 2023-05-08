import logging
from pathlib import Path
from textwrap import dedent

import aiofiles
from aiofiles.tempfile import TemporaryDirectory
from DIRAC import gLogger, initialize
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import (
    JobMonitoringClient,
)
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient

from bartender.async_utils import async_wrap
from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.dirac_config import DiracSchedulerConfig

# Keys from
# https://github.com/DIRACGrid/DIRAC/blob/integration/src/DIRAC/WorkloadManagementSystem/Client/JobStatus.py
dirac_status_map: dict[str, State] = {
    "Submitting": "queued",
    "Received": "queued",
    "Checking": "queued",
    "Staging": "queued",
    "Waiting": "queued",
    "Matched": "queued",
    "Rescheduled": "queued",
    "Running": "running",
    "Stalled": "running",
    "Completing": "running",
    "Done": "ok",
    "Completed": "ok",
    "Failed": "error",
    "Deleted": "error",
    "Killed": "error",
}


logger = logging.getLogger(__file__)


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
        # to submit requires a jdl and shell script to be created locally
        # the description.job_dir is on grid storage so cannot be used.
        # so create a temporary directory to write the jdl and shell script
        async with TemporaryDirectory(prefix="bartender-scriptdir") as scriptdir:
            jdl = await self._jdl_script(description, Path(scriptdir))

            async_submit = async_wrap(self.wms_client.submitJob)
            result = await async_submit(jdl)
            if not result["OK"]:
                raise RuntimeError(result["Message"])
            job_id = result["Value"]
            logger.warning(f"Job submitted with ID: {job_id}")
            return job_id

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

    async def _job_script(self, description: JobDescription, scriptdir: Path) -> Path:
        file = Path(scriptdir / "job.sh")
        # default OutputSandboxLimit is 10Mb which is too small sometimes,
        # so always upload output dir to grid storage as archive
        script = self._job_script_content(description)
        logger.warning(f"Writing job script to {file}, containing {script}")
        async with aiofiles.open(file, "w") as handle:
            await handle.write(script)
        return file

    def _job_script_content(self, description: JobDescription) -> str:
        stage_in = self._stage_in_script(description)
        stage_out = self._stage_out_script(description)
        command = self._command_script(description)
        return dedent(
            f"""\
            #!/bin/bash
            set -e
            {stage_in}
            {command}
            {stage_out}
            """,
        )

    def _stage_in_script(self, description: JobDescription) -> str:
        # TODO dedup tar filenames here and in filesystem
        fn = "input.tar"
        fn_on_grid = description.job_dir / fn
        return dedent(
            f"""\
            # Download & unpack input files
            dirac-dms-get-file {fn_on_grid}
            tar -xf {fn}
            rm {fn}
            find . -type f > .input_files.txt
            """,
        )

    def _stage_out_script(self, description: JobDescription) -> str:
        # TODO dedup tar filename here and in filesystem
        fn = "output.tar"
        fn_on_grid = description.job_dir / fn
        se = self.config.storage_element
        return dedent(
            f"""\
            # Pack & upload output files
            echo {fn} >> .input_files.txt
            tar -cf {fn} --exclude-from=.input_files.txt .
            dirac-dms-add-file {fn_on_grid} {fn} {se}
            rm {fn}
            """,
        )

    def _command_script(self, description: JobDescription) -> str:
        command = description.command
        if self.config.apptainer_image:
            image = self.config.apptainer_image
            command = f"apptainer run {image} {description.command}"
        return dedent(
            f"""\
            # Run command
            ({command}) > stdout.txt 2> stderr.txt
            echo -n $? > returncode
            """,
        )

    async def _jdl_script(self, description: JobDescription, scriptdir: Path) -> str:
        jobsh = await self._job_script(description, scriptdir)
        abs_job_sh = jobsh.absolute()

        job_name = _external_id_from_job_dir(description.job_dir)
        # TODO add input.tar in inputsandbox instead of dirac-dms-get-file
        # TODO add output.tar in OutputData+OutputSE instead of dirac-dms-add-file
        # TODO add method to fetch jobstdout.txt and jobstderr.txt,
        # now impossible to see job script output.
        # The command output in stored in output.tar.
        # For now use `dirac-wms-job-get-output <job id>` command.
        return dedent(
            f"""\
            JobName = "{job_name}";
            Executable = "{jobsh.name}";
            InputSandbox = {{"{abs_job_sh}"}};
            StdOutput = "jobstdout.txt";
            StdError = "jobstderr.txt";
            OutputSandbox = {{ "jobstdout.txt", "jobstderr.txt" }};
            """,
        )

    async def _write_jdl_script(self, scriptdir: Path, script: str) -> Path:
        file = scriptdir / "job.jdl"
        logger.warning(f"Writing job jdl to {file}, containing {script}")
        async with aiofiles.open(file, "w") as handle:
            await handle.write(script)
        return file


# TODO move to JobDescription as property
def _external_id_from_job_dir(job_dir: Path) -> str:
    return job_dir.name
