from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from pathlib import Path
from typing import Any, Optional, Protocol

from asyncssh import SSHClientConnection

from bartender._ssh_utils import SshConnectConfig, ssh_connect


class CommandRunner(Protocol):
    """Protocol for running a command."""

    async def run(
        self,
        command: str,
        args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> tuple[int, str, str]:
        """Run command.

        :param command: Command to execute. Command can not contain spaces.
        :param args: List of arguments for command.
            Argument containing spaces should be wrapped in quotes.
        :param stdin: Input for command.
        :param cwd: In which directory the command should be run.
        :return: Tuple with return code, stdout and stderr.
        """  # noqa: DAR202

    def close(self) -> None:
        """Close any connections runner has."""


class LocalCommandRunner(CommandRunner):
    """Runs command on system where current Python process is running."""

    async def run(
        self,
        command: str,
        args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> tuple[int, str, str]:
        """Run command.

        :param command: Command to execute. Command can not contain spaces.
        :param args: List of arguments for command.
            Argument containing spaces should be wrapped in quotes.
        :param stdin: Input for command.
        :param cwd: In which directory the command should be run.
        :raises ValueError: Command is both running and dead.
        :return: Tuple with return code, stdout and stderr.
        """
        proc = await create_subprocess_exec(
            command,
            *args,
            stdout=PIPE,
            stderr=PIPE,
            cwd=cwd,
        )
        if stdin is None:
            (stdout, stderr) = await proc.communicate()
        else:
            (stdout, stderr) = await proc.communicate(stdin.encode("utf-8"))
        if proc.returncode is None:
            raise ValueError("Unkown return code")
        return (proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8"))

    def close(self) -> None:
        """Close any connections runner has."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LocalCommandRunner)


class SshCommandRunner(CommandRunner):
    """Run command on a remote machine using SSH."""

    def __init__(
        self,
        config: SshConnectConfig,
    ):
        """Constructor.

        :param config: SSH connection configuration.
        """
        self.config = config
        self.conn: Optional[SSHClientConnection] = None

    async def run(
        self,
        command: str,
        args: list[str],
        stdin: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> tuple[int, str, str]:
        """Run command.

        :param command: Command to execute. Command can not contain spaces.
        :param args: List of arguments for command.
            Argument containing spaces should be wrapped in quotes.
        :param stdin: Input for command.
        :param cwd: In which directory the command should be run.
        :raises ValueError: Command is both running and dead.
        :return: Tuple with return code, stdout and stderr.
        """
        remote_command = command
        if args:
            joined_args = " ".join(args)
            remote_command = f"{remote_command} {joined_args}"
        if cwd is not None:
            remote_command = f"cd {cwd} && {remote_command}"

        if self.conn is None:
            self.conn = await ssh_connect(self.config)

        result = await self.conn.run(remote_command, input=stdin)
        if (  # noqa: WPS337
            result.returncode is None
            or not isinstance(result.stdout, str)
            or not isinstance(result.stderr, str)
        ):
            raise ValueError(
                "Unknown return code or incorrect format of stdout or stderr",
            )
        return (result.returncode, result.stdout, result.stderr)

    def close(self) -> None:
        """Close any connections runner has."""
        if self.conn:
            self.conn.close()

    def __enter__(self) -> "SshCommandRunner":
        return self

    def __exit__(self, *args: list[Any]) -> None:
        self.close()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SshCommandRunner) and self.config == other.config

    def __repr__(self) -> str:
        return f"SshCommandRunner(config={self.config})"
