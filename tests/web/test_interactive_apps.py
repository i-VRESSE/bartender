from pathlib import Path
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
