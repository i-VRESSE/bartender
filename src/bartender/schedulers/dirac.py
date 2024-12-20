import logging
import tarfile
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from typing import Tuple

import aiofiles
from aiofiles.tempfile import TemporaryDirectory
from DIRAC.Core.Utilities.ReturnValues import DReturnType
from DIRAC.WorkloadManagementSystem.Client.JobMonitoringClient import (
    JobMonitoringClient,
)
from DIRAC.WorkloadManagementSystem.Client.SandboxStoreClient import SandboxStoreClient
from DIRAC.WorkloadManagementSystem.Client.WMSClient import WMSClient

from bartender.async_utils import async_wrap
from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.dirac_config import DiracSchedulerConfig
from bartender.shared.dirac import setup_proxy_renewer, teardown_proxy_renewer

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
        setup_proxy_renewer(config.proxy)
        self.wms_client = WMSClient()
        self.monitoring = JobMonitoringClient()

    async def submit(self, description: JobDescription) -> str:
        """Submit a job description for running.

        The job submitted to DIRAC will do the following:

        1. Download `description.job_dir / input.tar` from grid storage.
        2. Unpack `input.tar`.
        3. Run `description.command`
            * Capturing stdout and stderr as stdout.txt and stderr.txt files.
            * Capturing return code in return_code file.
        4. Pack `output.tar`.
            * Excluding files from input.tar.
        5. Upload `output.tar` to grid storage as `description.job_dir / output.tar`.

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
            return str(job_id)

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
        result = await async_state(int(job_id))
        if not result["OK"]:
            raise RuntimeError(result["Message"])
        dirac_status = result["Value"][int(job_id)]["Status"]
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
        # DIRAC returns integer for job id, so convert string to integer
        return [
            dirac_status_map[result["Value"][int(job_id)]["Status"]]
            for job_id in job_ids
        ]

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
        if not result["OK"]:
            raise RuntimeError(result["Message"])

    async def close(self) -> None:
        """Close scheduler."""
        await teardown_proxy_renewer()

    async def logs(self, job_id: str, job_dir: Path) -> Tuple[str, str]:
        """Get stdout and stderr of a job.

        If job has not completed, then will raise an exception.
        If job completed succesfully, then stdout,txt and stderr.txt are read
        from job_dir.
        If job failed, then stdout and stderr are read from grid storage.

        Logs of a failed job includes logs of unpacking/packing the
        input and output files.

        The logs can be fetched on command line
        with `dirac-wms-job-get-output <job id>`.

        Args:
            job_id: Identifier of job.
            job_dir: Directory where stdout.txt and stderr.txt files
                of job are stored.

        Raises:
            RuntimeError: When fetching of logs fails.

        Returns:
            Tuple of stdout and stderr.
        """
        try:
            return await super().logs(job_id, job_dir)
        except FileNotFoundError:
            logger.info("Failed to fetch logs from job_dir, trying grid storage")
        download_sandbox = async_wrap(SandboxStoreClient().downloadSandboxForJob)
        sandbox: DReturnType[bytes] = await download_sandbox(
            job_id,
            "Output",
            inMemory=True,
        )
        if "Message" in sandbox:
            message = sandbox.get("Message")
            raise RuntimeError(f"Failed to fetch logs for {job_id}: {message}")
        sandbox_bytes = sandbox["Value"]
        with tarfile.open(fileobj=BytesIO(sandbox_bytes)) as tar:
            await _extract_text_file(tar, "jobstdout.txt", job_dir / "stdout.txt")
            await _extract_text_file(tar, "jobstderr.txt", job_dir / "stderr.txt")
            return await super().logs(job_id, job_dir)

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
        command = self._command_script(description)
        # TODO when command has non-zero return code then
        # output.tar is not uploaded,
        # you can get logs with scheduduler.raw_logs()
        # but output.tar is gone, wouild be nice to have it
        # see possible options at
        # https://github.com/i-VRESSE/bartender/pull/72
        return dedent(
            f"""\
            #!/bin/bash
            # Unpack input files
            tar -xf input.tar
            rm input.tar
            find . -type f > .input_files.txt
            {command}
            # Pack output files
            echo output.tar >> .input_files.txt
            tar -cf output.tar --exclude-from=.input_files.txt .
            exit $(cat returncode)
            """,
        )

    def _command_script(self, description: JobDescription) -> str:
        command = description.command
        if self.config.apptainer_image:
            image = self.config.apptainer_image
            # TODO if command is complex then qoutes are likely needed
            command = f"apptainer run {image} {description.command}"
        # added echo so DIRAC
        # uploads sandbox and output.tar
        # if stdout and stderr are empty then
        # sandbox (containing jobstderr.txt and jobstdout.txt)
        # is not uploaded and uploading output.tar fails due to
        # UnboundLocalError: local variable 'result_sbUpload'

        # added cat of stdout.txt and stderr.txt
        # so if job fails then logs are available in output sandbox.
        return dedent(
            f"""\
            # Run command
            echo 'Running command for {description.job_dir}'
            ({command}) > stdout.txt 2> stderr.txt
            echo -n $? > returncode
            cat stdout.txt
            cat stderr.txt >&2
            """,
        )

    async def _jdl_script(self, description: JobDescription, scriptdir: Path) -> str:
        jobsh = await self._job_script(description, scriptdir)
        abs_job_sh = jobsh.absolute()

        job_name = description.job_dir.name
        # jobstdout.txt and jobstderr.txt contain logs of whole job
        # including logs of execution of command.

        # OutputPath must be relative to user's home directory
        # to prevent files being uploaded outside user's home directory.
        output_path = _relative_output_dir(description)
        return dedent(
            f"""\
            JobName = "{job_name}";
            Executable = "{jobsh.name}";
            InputSandbox = {{"{abs_job_sh}"}};
            InputData = {{ "{description.job_dir}/input.tar" }};
            InputDataModule = "DIRAC.WorkloadManagementSystem.Client.InputDataResolution";
            InputDataPolicy = "DIRAC.WorkloadManagementSystem.Client.DownloadInputData";
            OutputData = {{ "output.tar" }};
            OutputSE = {{ "{self.config.storage_element}" }};
            OutputPath = "{output_path}";
            StdOutput = "jobstdout.txt";
            StdError = "jobstderr.txt";
            OutputSandbox = {{ "jobstdout.txt", "jobstderr.txt" }};
            """,  # noqa: E501, WPS237, WPS318
        )


def _relative_output_dir(description: JobDescription) -> Path:
    """Return description.output_dir relative to user's home directory.

    user home directory is /<vo>/user/<initial>/<user>
    to write /tutoVO/user/c/ciuser/bartenderjobs/job1/input.tar
    OutputPath must be bartenderjobs/job1

    Args:
        description: Description of job.

    Returns:
        .description.output_dir relative to user's home directory.
    """
    nr_home_dir_parts = 5
    return Path(*description.job_dir.parts[nr_home_dir_parts:])


async def _extract_text_file(tar: tarfile.TarFile, src: str, target: Path) -> None:
    """Extract text file from tarfile.

    Args:
        tar: Tarfile to extract file from.
        src: Name of file to extract.
        target: Path to write file to.
    """
    aextract = async_wrap(tar.extract)
    await aextract(src, target.parent)
    (target.parent / src).rename(target)
