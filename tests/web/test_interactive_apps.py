from base64 import b64encode
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from jsonschema import ValidationError

from bartender.web.api.job.interactive_apps import (
    InteractiveApplicationConfiguration,
    build_command,
    run,
)


@pytest.fixture
def app_config() -> InteractiveApplicationConfiguration:
    return InteractiveApplicationConfiguration(
        command="cat {{ input_file|q }} | wc -m  > {{ output_file|q }}",
        input={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "input_file": {"type": "string"},
                "output_file": {"type": "string"},
            },
            "required": ["input_file", "output_file"],
        },
        timeout=10,
    )


@pytest.fixture
def job_dir(tmp_path: Path) -> Path:
    input_file = tmp_path / "input.txt"
    input_file.write_text("hello world")
    return tmp_path


@pytest.mark.anyio
async def test_run(
    job_dir: Path,
    app_config: InteractiveApplicationConfiguration,
) -> None:
    payload = {"input_file": "input.txt", "output_file": "output.txt"}
    result = await run(job_dir, payload, app_config)
    assert result.returncode == 0
    assert (job_dir / "output.txt").read_text() == "11\n"


@pytest.mark.anyio
async def test_run_invalid_payload(
    job_dir: Path,
    app_config: InteractiveApplicationConfiguration,
) -> None:
    payload: dict[Any, Any] = {}
    with pytest.raises(ValidationError, match="'input_file' is a required property"):
        await run(job_dir, payload, app_config)


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {"input_file": "input.txt", "output_file": "output.txt"},
            "cat input.txt | wc -m  > output.txt",
        ),
        # check that shell injection is not possible
        (
            {"input_file": "input.txt; rm -rf /", "output_file": "output.txt"},
            "cat 'input.txt; rm -rf /' | wc -m  > output.txt",
        ),
    ],
)
def test_build_command(
    app_config: InteractiveApplicationConfiguration,
    payload: dict[Any, Any],
    expected: str,
) -> None:
    command = build_command(payload, app_config)
    assert command == expected


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {},
            "ls",
        ),
        (
            {"recursive": True},
            "ls --recursive",
        ),
        (
            {"recursive": False},
            "ls",
        ),
    ],
)
def test_build_command_optional_field(payload: dict[Any, Any], expected: str) -> None:
    config = InteractiveApplicationConfiguration(
        command="ls{% if recursive %} --recursive{% endif %}",
        input={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "recursive": {"type": "boolean"},
            },
        },
    )
    command = build_command(payload, config)
    assert command == expected


def test_build_command_lookup() -> None:
    template = """\
        {% set flag = {
            'lines': '-l',
            'words': '-w',
            'chars': '-m',
            'bytes': '-c',
        }[what] %}
        cat README.md | wc {{ flag|q }} > README.md.count"""
    config = InteractiveApplicationConfiguration(
        command=dedent(template),
        input={
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "what": {
                    "type": "string",
                    "enum": ["lines", "words", "chars", "bytes"],
                    "default": "lines",
                },
            },
        },
    )
    payload = {"what": "words"}
    command = build_command(payload, config)
    assert command == "cat README.md | wc -w > README.md.count"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "encoding, content",
    [
        (
            {"contentEncoding": "base64"},
            b64encode(b"hello world").decode(),
        ),
        (
            {},
            "hello world",
        ),
    ],
)
async def test_run_with_embedded_files(
    job_dir: Path,
    content: str,
    encoding: dict[str, str],
) -> None:
    template = "cmp {{ file1|q }} {{ file2|q }}"
    input_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "file1": {"type": "string", "title": "File in job directory"},
            "file2": {
                "type": "string",
                "title": "Embedded file to compare file1 with",
                "contentMediaType": "text/plain",
                **encoding,
            },
        },
        "required": ["file1", "file2"],
    }
    config = InteractiveApplicationConfiguration(
        command=dedent(template),
        input=input_schema,
    )
    payload = {
        "file1": "input.txt",
        "file2": content,
    }
    result = await run(job_dir, payload, config)
    assert result.returncode == 0
