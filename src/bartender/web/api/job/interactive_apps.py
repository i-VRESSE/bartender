from asyncio import create_subprocess_shell, wait_for
from asyncio.subprocess import PIPE
from pathlib import Path
from shlex import quote
from string import Template

from jsonschema import Draft202012Validator
from pydantic import BaseModel

from bartender.config import InteractiveApplicationConfiguration

"""
Notes for self:

Pros:
* Can use job directory without having to copy stuff around
Cons:
* Each interactiveapp will have own openapi endpoint.
    The generated openapi client will be specific to bartender instance.
    To use bartender with haddock3-webapp (which has generated client)
    you already need to configure haddock3 as application in config.yaml
    so this is not a big deal.
* Different then rest of bonvinlab apps.
* Trust interactiveapp to not do anything wrong in job directory.
"""


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


def _build_command(payload: object, app: InteractiveApplicationConfiguration) -> str:
    # TODO rewrap validation exception into HTTPValidationError
    # TODO cache validator
    validator = Draft202012Validator(app.input)
    validator.validate(payload)

    # TODO to allow nested payload we could use a Jinja2 template
    # but need to be careful with newlines
    return Template(app.command).substitute(
        {key: quote(value) for key, value in payload.items()},
    )


async def run(
    job_dir: Path,
    payload: object,
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
    command = _build_command(payload, app)
    return await _shell(job_dir, command, timeout=app.timeout)
    # TODO return path where results of command are stored
    # TODO to not overload the system limit number of concurrent running shell commands
