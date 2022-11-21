from textwrap import dedent
from typing import Optional

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.schedulers.runner import CommandRunner


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
        # fallback to error when slurm state code is unmapped.
        return "error"


class SlurmScheduler(AbstractScheduler):
    """Slurm batch scheduler."""

    def __init__(
        self,
        runner: CommandRunner,
        partition: Optional[str] = None,
        time: Optional[str] = None,
        extra_options: Optional[list[str]] = None,
    ):
        """Constructor.

        :param runner: Runner for running commands. Can be local or ssh.
        :param partition: Partition in which all jobs should be submitted.
        :param time: Limit on the total run time of the job.
        :param extra_options: Escape hatch to add extra options to job script.
            The string `#SBATCH {extra_options[0]}` will be appended to job script.
        """
        # TODO which option should be set to per scheduler or per job description?
        self.runner = runner
        self.partition = partition
        self.time = time
        if extra_options is None:
            self.extra_options = []
        else:
            self.extra_options = extra_options

    async def submit(self, description: JobDescription) -> str:  # noqa: D102):
        # TODO if runner is a SSHCommandRunner then description.jobdir
        # must be on a shared filesystem or remote filesystem
        script = self._submit_script(description)
        command = "sbatch"
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

        return stdout.strip().split(" ")[-1]

    async def state(self, job_id: str) -> State:
        """Get state of a job.

        Once job is completed, then scheduler can forget job.

        :param job_id: Identifier of job.
        :return: State of job.
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

        :param job_id: Identifier of job.
        """
        command = "scancel"
        args = [job_id]
        await self.runner.run(command, args)
        # TODO check if succesfull

    async def close(self) -> None:
        """Cancel all runnning jobs and make scheduler unable to work."""
        self.runner.close()

    async def _state_from_accounting(self, job_id: str) -> str:
        command = "sacct"
        args = ["-j", job_id, "--noheader", "--format=state"]
        (returncode, stdout, stderr) = await self.runner.run(command, args)
        if returncode != 0:
            raise RuntimeError(
                f"Error running sacct, exited with {returncode}: {stderr}",
            )
        return stdout

    def _submit_script(self, description: JobDescription) -> str:
        partition_line = ""
        if self.partition:
            partition_line = f"#SBATCH --partition={self.partition}"
        time_line = ""
        if self.time:
            time_line = f"#SBATCH --time={self.time}"

        # TODO filter out options already set
        extra_option_lines = "\n".join(
            [f"#SBATCH {extra}" for extra in self.extra_options],
        )
        script = f"""\
            #!/bin/bash
            {extra_option_lines}
            {partition_line}
            {time_line}
            #SBATCH --output=stdout.txt
            #SBATCH --error=stderr.txt
            {description.command}
            echo -n $? > returncode
        """
        return dedent(script)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SlurmScheduler)
            and self.runner == other.runner
            and self.partition == other.partition
            and self.time == other.time
            and self.extra_options == other.extra_options
        )

    def __repr__(self) -> str:
        return f"SlurmScheduler(runner={self.runner}, partition={self.partition}, time={self.time}, extra_options={self.extra_options})"
