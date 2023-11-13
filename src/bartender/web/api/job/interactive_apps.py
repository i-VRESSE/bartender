from asyncio import create_subprocess_shell, wait_for
from asyncio.subprocess import PIPE
from pathlib import Path
from shlex import quote
from typing import Any

from jinja2 import Environment
from jsonschema import Draft202012Validator
from pydantic import BaseModel

from bartender.config import InteractiveApplicationConfiguration


class InteractiveAppResult(BaseModel):
    """Represents the result of running a InteractiveApp.

    Attributes:
        returncode: The return code of the InteractiveApp process.
        stderr: The standard error output of the InteractiveApp process.
        stdout: The standard output of the InteractiveApp process.
    """

    returncode: int
    stderr: str
    stdout: str


async def _shell(job_dir: Path, command: str, timeout: float) -> InteractiveAppResult:
    """Executes a shell command in the specified job directory.

    Args:
        job_dir: The path to the job directory.
        command: The shell command to execute.
        timeout: The maximum time to wait for the command to finish.

    Returns:
        The result of running the shell command.
    """
    proc = await create_subprocess_shell(
        command,
        cwd=job_dir,
        stdout=PIPE,
        stderr=PIPE,
    )
    stdout, stderr = await wait_for(proc.communicate(), timeout=timeout)
    return InteractiveAppResult(
        returncode=proc.returncode,
        stderr=stderr.decode(),
        stdout=stdout.decode(),
    )


template_environment = (
    Environment()  # noqa: S701 -- used to generate shell commands not HTML
)
template_environment.filters["q"] = lambda variable: quote(str(variable))


def build_command(
    payload: dict[Any, Any],
    app: InteractiveApplicationConfiguration,
) -> str:
    """Builds a command string for an interactive application.

    Args:
        payload: A dictionary containing the input data for the application.
        app: An object containing the configuration for the interactive application.

    Returns:
        str: A string representing the command to be executed.
    """
    # TODO rewrap validation exception into HTTPValidationError
    # TODO cache validator
    validator = Draft202012Validator(app.input)
    validator.validate(payload)

    template = template_environment.from_string(app.command)
    return template.render(**payload)


async def run(
    job_dir: Path,
    payload: dict[Any, Any],
    app: InteractiveApplicationConfiguration,
) -> InteractiveAppResult:
    """
    Runs an interactive application with the given payload and configuration.

    Args:
        job_dir: The directory where the input files for the application are located.
        payload: The payload to be used for the interactive application.
        app: The configuration for the interactive application.

    Returns:
        The result of running the interactive application.
    """
    command = build_command(payload, app)
    return await _shell(job_dir, command, timeout=app.timeout)
    # TODO return path where results of command are stored
    # TODO to not overload the system limit number of concurrent running shell commands
