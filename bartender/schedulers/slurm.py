from abc import ABC, abstractmethod
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from textwrap import dedent
from typing import IO, Any, Optional, Union

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription


class Terminal(ABC):
    @abstractmethod
    async def exec(
        command: str,
        *args: list[str],
        stdout: Union[None, PIPE, str],
        stderr: Union[None, PIPE, str] = None,
        cwd: str = None,
    ) -> tuple(str, str, str):
        """Execute command."""


class LocalTerminal(Terminal):
    async def exec(
        command: str,
        *args: list[str],
        stdin: Union[None, int, IO[Any]] = None,
        stdout: Union[None, int, IO[Any]] = None,
        stderr: Union[None, int, IO[Any]] = None,
        cwd: str = None,
    ) -> tuple(str, str, str):
        proc = await create_subprocess_exec(
            command, *args, stdout=stdout, stderr=stderr, cwd=cwd
        )
        if stdout is None and stderr is None:
            returncode = await proc.wait()
            return (returncode, "", "")
        else:
            (stdout, stderr) = await proc.communicate(stdin)
            return (proc.returncode, stdout, stderr)


class SSHTerminal(Terminal):
    async def exec(
        command: str,
        *args: list[str],
        stdin: Union[None, int, IO[Any]] = None,
        stdout: Union[None, int, IO[Any]] = None,
        stderr: Union[None, int, IO[Any]] = None,
        cwd: str = None,
    ) -> tuple(str, str, str):
        # TODO find ssh client
        raise NotImplementedError()


class SlurmScheduler(AbstractScheduler):
    def __init__(
        self,
        terminal: Terminal,
        partition: Optional[str] = None,
        time: Optional[str] = None,
        extra_options: list[str] = [],
    ):
        # TODO which option should be set to per scheduler or per job description?
        self.terminal = terminal
        self.partition = partition
        self.time = time
        self.extra_options = extra_options

    async def submit(self, description: JobDescription) -> str:  # noqa: D102):
        script = self._submit_script(description)
        command = "sbatch"
        proc = await create_subprocess_exec(
            command,
            stdout=PIPE,
            stderr=PIPE,
            cwd=description.job_dir,
        )
        (stdout, stderr) = await proc.communicate(script)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Error running sbatch, exited with {proc.returncode}: {stderr}",
            )

        job_id = stdout.strip().split(" ")[-1]
        return job_id

    async def state(self, job_id: str) -> State:
        command = "squeue"
        args = ["-j", job_id, "--noheader", "--format=%T"]
        proc = await create_subprocess_exec(
            command,
            *args,
            stdout=PIPE,
            stderr=PIPE,
        )
        (stdout, stderr) = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Error running squeue, exited with {proc.returncode}: {stderr}",
            )
        slurm_state = stdout.strip()
        # See https://slurm.schedmd.com/squeue.html#SECTION_JOB-STATE-CODES
        status_map: dict[str, State] = {
            "PENDING": "queued",
            "CONFIGURING": "queud",
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

    async def cancel(self, job_id: str) -> None:
        command = "scancel"
        args = [job_id]
        proc = await create_subprocess_exec(
            command,
            *args,
        )
        await proc.wait()
        # TODO check if succesfull

    def _submit_script(self, description: JobDescription) -> str:
        partition_line = ""
        if self.partition:
            partition_line = f"#SBATCH --partition={self.partition}"
        time_line = ""
        if self.time:
            time_line = f"#SBATCH --time={self.time}"

        # TODO filter out options already set
        extra_option_lines = [f"#SBATCH {extra}\n" for extra in self.extra_options]
        script = dedent(
            f"""#!/bin/bash
        {extra_option_lines}
        {partition_line}
        {time_line}
        #SBATCH -output=stdout.txt
        #SBATCH -error=stderr.txt
        cd {description.job_dir}
        {description.command}
        echo -n $? > returncode
        """,
        )
        return script
