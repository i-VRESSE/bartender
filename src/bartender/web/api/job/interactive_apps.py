"""Module for running interactive applications."""
from asyncio import create_subprocess_shell, wait_for
from asyncio.subprocess import PIPE
from base64 import b64decode
from contextlib import asynccontextmanager
from os.path import join
from pathlib import Path
from typing import Any, AsyncGenerator, Literal, Union

from aiofiles import open
from aiofiles.tempfile import TemporaryDirectory
from jsonschema import Draft202012Validator
from pydantic import BaseModel

from bartender.config import InteractiveApplicationConfiguration
from bartender.template_environment import template_environment


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
            In seconds.

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
    validator = Draft202012Validator(app.input_schema)
    validator.validate(payload)

    template = template_environment.from_string(app.command_template)
    return template.render(**payload)


MediaEncoding = Union[Literal["base64"], Literal["utf-8"]]


def encoding_of_prop(prop: dict[Any, Any]) -> Union[MediaEncoding, None]:
    """
    Determines the encoding of a property.

    Args:
        prop (dict): The property to determine the encoding of.

    Returns:
        The encoding of the property,
        or None if it is encoded with UTF-8,
        or False if it has no encoding.


    Raises:
        ValueError: If the encoding is not supported.
    """
    if prop.get("type") == "string" and prop.get("contentMediaType"):
        encoding = prop.get("contentEncoding", "utf-8")
        if encoding not in {"base64", "utf-8"}:
            raise ValueError(f"Unsupported content encoding {encoding}")
        return encoding
    return None


def media_in_schema(schema: Any) -> dict[str, MediaEncoding]:
    """
    Extracts properties from JSON schema that store media.

    See https://json-schema.org/understanding-json-schema/reference/non_json_data

    Args:
        schema: The JSON schema to extract from.

    Returns:
        dict: A dictionary containing the property path and their encoding.
    """
    medias: dict[str, MediaEncoding] = {}
    if not isinstance(schema, dict):
        return medias
    if schema.get("type") != "object":
        return medias
    if "properties" not in schema:
        return medias
    for key, value in schema["properties"].items():
        if encoding := encoding_of_prop(value):
            medias[key] = encoding
        # TODO make nested for objects, arrays, tuples, etc.
    return medias


async def write_file(encoded_data: str, encoding: MediaEncoding, fn: str) -> None:
    """Stages a file to disk.

    Args:
        encoded_data: The encoded data to be written to disk.
        encoding: The encoding of the encoded data.
        fn: The path to the file to be written.
    """
    async with open(fn, "wb") as fh:
        if encoding == "base64":
            # TODO run async in thread pool
            decoded_data = b64decode(encoded_data)
        else:
            # Treat as plain text
            decoded_data = encoded_data.encode()
        # TODO dont store in memory, stream it
        await fh.write(decoded_data)


def get_path_in_payload(data: dict[Any, Any], path: str) -> Union[Any, None]:
    """
    Get the value at the specified path in the given dictionary.

    Args:
        data: The dictionary or list to search for the value.
        path: The path to the value, separated by dots.
            Can be nested. For example, "foo.bar.1" will set the value of
            data["foo"]["bar"][1].

    Returns:
        The value at the specified path, or None if the path does not exist.
    """
    # TODO make nested
    return data.get(path)


def set_path_in_payload(data: dict[Any, Any], path: str, value: Any) -> None:
    """
    Sets the value of a path in a dictionary.

    Args:
        data: The dictionary to modify.
        path: The path to set the value for.
            Can be nested. For example, "foo.bar.1" will set the value of
            data["foo"]["bar"][1].
        value: The value to set for the path.

    Returns:
        None
    """
    # TODO make nested
    # TODO dont change in-place, return new dict
    data[path] = value


async def stage_embedded_file(
    payload: dict[Any, Any],
    path: str,
    encoding: MediaEncoding,
    media_dir: str,
) -> None:
    """Stage embedded file.

    Extracts an embedded file from the given payload,
    writes it to disk in the specified media directory,
    and updates the payload to reference the newly written file.

    Args:
        payload: The payload containing the embedded file.
        path: The path to the embedded file within the payload.
        encoding: The encoding of the embedded file.
        media_dir: The directory in which to write the extracted file.
    """
    encoded_data = get_path_in_payload(payload, path)
    if not encoded_data:
        return
    fn = join(media_dir, path)
    await write_file(encoded_data, encoding, fn)
    set_path_in_payload(payload, path, fn)


@asynccontextmanager
async def stage_embedded_files(
    payload: dict[Any, Any],
    schema: dict[Any, Any],
) -> AsyncGenerator[None, None]:
    """Stages embedded files in the payload to disk.

    Args:
        payload: A dictionary containing the input data for the application.
        schema: The schema for the payload

    Yields:
        Nothing.
    """
    medias = media_in_schema(schema)
    if not medias:
        # no embedded files to stage
        yield
        return
    async with TemporaryDirectory() as media_dir:
        for path, encoding in medias.items():
            await stage_embedded_file(payload, path, encoding, media_dir)
        yield


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
    async with stage_embedded_files(payload, app.input_schema):
        command = build_command(payload, app)
        return await _shell(job_dir, command, timeout=app.timeout)
