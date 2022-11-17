from abc import ABC, abstractmethod
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from textwrap import dedent
from typing import Optional

from asyncssh import connect

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription


class CommandRunner(ABC):
    @abstractmethod
    async def run(
        command: str,
        *args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> tuple[int, str, str]:
        """Run command.

        :param command: Command to execute. Command can not contain spaces.
        :param args: List of arguments for command. Argument containing spaces should be wrapped in quotes.
        :param stdin: Input for command.
        :param cwd: In which directory the command should be run.
        :return: Tuple with return code, stdout and stderr.
        """


class LocalCommandRunner(CommandRunner):
    async def run(
        self,
        command: str,
        *args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> tuple[int, str, str]:
        proc = await create_subprocess_exec(
            command, *args, stdout=PIPE, stderr=PIPE, cwd=cwd
        )
        (stdout, stderr) = await proc.communicate(stdin)
        return (proc.returncode, stdout, stderr)


class SSHCommandRunner(CommandRunner):
    def __init__(
        self,
        hostname: str,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password
        self.conn = None

    async def _connect(self):
        conn_vargs = {
            "known_hosts": None,
        }
        if self.password is not None:
            conn_vargs["agent_path"] = None

        self.conn = await connect(
            host=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            **conn_vargs,
        )

    async def run(
        self,
        command: str,
        *args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> tuple[int, str, str]:
        remote_command = command
        if args:
            remote_command = f'{remote_command} {" ".join(args)}'
        if cwd is not None:
            remote_command = f"cd {cwd} && {remote_command}"

        if self.conn is None:
            await self._connect()

        result = await self.conn.run(remote_command, input=stdin)

        print((command, args, result.returncode, result.stdout, result.stderr))
        return (result.returncode, result.stdout, result.stderr)

    def __del__(self):
        self.close()

    def close(self):
        if self.conn:
            self.conn.close()


class SlurmScheduler(AbstractScheduler):
    def __init__(
        self,
        runner: CommandRunner,
        partition: Optional[str] = None,
        time: Optional[str] = None,
        extra_options: list[str] = [],
    ):
        # TODO which option should be set to per scheduler or per job description?
        self.runner = runner
        self.partition = partition
        self.time = time
        self.extra_options = extra_options

    async def submit(self, description: JobDescription) -> str:  # noqa: D102):
        # TODO check that if runniner is a SSHCommandRunner then description.jobdir must be on a shared filesystem
        script = self._submit_script(description)
        print(script)
        command = "sbatch"
        # command = 'hostname'
        (returncode, stdout, stderr) = await self.runner.run(
            command,
            cwd=description.job_dir,
            stdin=script,
        )
        if returncode != 0:
            raise RuntimeError(
                f"Error running sbatch, exited with {returncode}: {stderr}",
            )

        job_id = stdout.strip().split(" ")[-1]
        return job_id

    async def state(self, job_id: str) -> State:
        command = "squeue"
        args = ["-j", job_id, "--noheader", "--format=%T"]
        (returncode, stdout, stderr) = await self.runner.run(command, *args)
        if returncode != 0 or stdout == "":
            print("squeue failed")
            # Completed jobs cannot be retrieved with squeue,
            # depending on whether slurm has configured accounting and job is not too old
            # the state can be requested using `sacct`
            command = "sacct"
            args = ["-j", job_id, "--noheader", "--format=state"]
            (returncode, stdout, stderr) = await self.runner.run(command, *args)
            if returncode != 0:
                raise RuntimeError(
                    f"Error running sacct, exited with {returncode}: {stderr}",
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
        await self.runner.run(command, *args)
        # TODO check if succesfull

    async def close(self):
        self.runner.close()

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
