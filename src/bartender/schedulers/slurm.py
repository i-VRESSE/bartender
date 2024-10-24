import logging
from textwrap import dedent
from typing import Literal, Optional

from pydantic import BaseModel

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.runner import (
    CommandRunner,
    LocalCommandRunner,
    SshCommandRunner,
)
from bartender.shared.ssh import SshConnectConfig

logger = logging.getLogger(__name__)


def _map_slurm_state(slurm_state: str) -> State:
    status_map: dict[str, State] = {
        "PENDING": "queued",
        "CONFIGURING": "queued",
        "RUNNING": "running",
        "SUSPENDED": "running",
        "COMPLETING": "running",
        "STAGE_OUT": "running",
        "CANCELLED": "error",
        "COMPLETED": "ok",
        "FAILED": "error",
        "TIMEOUT": "error",
        "PREEMPTED": "error",
        "NODE_FAIL": "error",
        "SPECIAL_EXIT": "error",
    }
    try:
        return status_map[slurm_state]
    except KeyError:
        logger.error(f"Unmapped slurm state code: {slurm_state}")
        # fallback to error when slurm state code is unmapped.
        return "error"


class SlurmSchedulerConfig(BaseModel):
    """Configuration for Slurm scheduler.

    Args:
        ssh_config: SSH connection configuration. When set will call
            SLURM commands on remote system via SSH connection. When not set
            will call SLURM commands on local system.
        partition: Partition in which all jobs should be submitted.
        time: Limit on the total run time of the job.
        extra_options: Escape hatch to add extra options to job script.
            The string `#SBATCH {extra_options[i]}` will be appended to job
            script.
        submitter_as_account: Use the submitter as the account to run the job.
    """

    type: Literal["slurm"] = "slurm"
    ssh_config: Optional[SshConnectConfig] = None
    partition: Optional[str] = None
    time: Optional[str] = None
    extra_options: Optional[list[str]] = None
    submitter_as_account: Optional[bool] = False


class SlurmScheduler(AbstractScheduler):
    """Slurm batch scheduler."""

    def __init__(self, config: SlurmSchedulerConfig):
        """Constructor.

        Args:
            config: Config for scheduler.
        """
        self.runner: CommandRunner = LocalCommandRunner()
        self.ssh_config = config.ssh_config
        if config.ssh_config is not None:
            self.runner = SshCommandRunner(config.ssh_config)
        self.partition = config.partition
        self.time = config.time
        if config.extra_options is None:
            self.extra_options = []
        else:
            self.extra_options = config.extra_options
        self.submitter_as_account = config.submitter_as_account

    async def submit(self, description: JobDescription) -> str:  # noqa: D102):
        # if runner is a SSHCommandRunner then description.jobdir
        # must be on a shared filesystem or remote filesystem
        script = self._submit_script(description)
        command = "sbatch"
        logger.debug(f"Submitting job with stdin: \n{script}")
        (returncode, stdout, stderr) = await self.runner.run(
            command,
            args=[],
            cwd=description.job_dir,
            stdin=script,
        )
        if returncode != 0:
            raise RuntimeError(
                f"Error running sbatch, exited with {returncode}: {stderr}",
            )

        #  Get the "4" out of string like "Submitted batch job 4"
        return stdout.strip().split(" ")[-1]

    async def state(self, job_id: str) -> State:
        """Get state of a job.

        Once job is completed, then scheduler can forget job.

        Args:
            job_id: Identifier of job.

        Returns:
            State of job.
        """
        args = ["-j", job_id, "--noheader", "--format=%T"]
        (returncode, stdout, stderr) = await self.runner.run("squeue", args)
        if returncode != 0 or stdout == "":
            # Completed jobs cannot be retrieved with squeue, depending on
            # whether slurm has configured accounting and job is not too old
            # the state can be requested using `sacct`
            stdout = await self._state_from_accounting(job_id)
        slurm_state = stdout.strip()
        # See https://slurm.schedmd.com/squeue.html#SECTION_JOB-STATE-CODES
        return _map_slurm_state(slurm_state)

    async def cancel(self, job_id: str) -> None:
        """Cancel a queued or running job.

        Once a queued job is cancelled, then the scheduler can forget job.

        Args:
            job_id: Identifier of job.
        """
        command = "scancel"
        args = [job_id]
        await self.runner.run(command, args)
        # TODO check if succesfull

    async def close(self) -> None:
        """Cancel all runnning jobs and make scheduler unable to work."""
        self.runner.close()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SlurmScheduler)  # noqa: WPS222
            and self.runner == other.runner
            and self.partition == other.partition
            and self.time == other.time
            and self.extra_options == other.extra_options
        )

    def __repr__(self) -> str:
        config = SlurmSchedulerConfig(
            ssh_config=self.ssh_config,
            partition=self.partition,
            time=self.time,
            extra_options=self.extra_options,
        )
        return f"SlurmScheduler(config={config})"

    async def _state_from_accounting(self, job_id: str) -> str:
        command = "sacct"
        args = ["-j", job_id, "--noheader", "--format=state", "--allocations"]
        (returncode, stdout, stderr) = await self.runner.run(command, args)
        if returncode != 0:
            raise RuntimeError(
                f"Error running sacct, exited with {returncode}: {stderr}",
            )
        return stdout

    def _submit_script(self, description: JobDescription) -> str:  # noqa: WPS210
        partition_line = ""
        if self.partition:
            partition_line = f"#SBATCH --partition={self.partition}"
        time_line = ""
        if self.time:
            time_line = f"#SBATCH --time={self.time}"
        account_line = ""
        if description.submitter != "" and self.submitter_as_account:
            account_line = f"#SBATCH --account={description.submitter}"
        job_name_line = ""
        if description.application != "":
            job_name_line = f"#SBATCH --job-name={description.application}"
        # TODO filter out options already set
        extra_option_lines = "\n".join(
            [f"#SBATCH {extra}" for extra in self.extra_options],
        )
        script = f"""\
            #!/bin/bash
            {extra_option_lines}
            {partition_line}
            {time_line}
            {account_line}
            {job_name_line}
            #SBATCH --output=stdout.txt
            #SBATCH --error=stderr.txt
            {description.command}
            echo -n $? > returncode
        """  # noqa: WPS221
        return dedent(script)
