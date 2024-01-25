from pathlib import Path
from typing import Any

import pytest

from bartender.config import ApplicatonConfiguration
from bartender.web.api.applications.submit import build_description


@pytest.mark.parametrize(
    "payload, command_template, expected",
    [
        ({"foo": "bar"}, "echo {{ foo }}", "echo bar"),
        ({"foo": "b a z"}, "echo {{ foo|q }}", "echo 'b a z'"),
        # for lists adding quote filter at end is probably not what we want,
        # but could open you up to injection attacks
        ({"foo": [1, 2, 3]}, "echo {{ foo|join(' ')|q }}", "echo '1 2 3'"),
        # use map to quote each element
        ({"foo": ["a b", "c"]}, "echo {{ foo|map('q')|join(' ') }}", "echo 'a b' c"),
    ],
)
def test_build_description(
    payload: dict[str, Any],
    command_template: str,
    expected: str,
    tmp_path: Path,
) -> None:
    job_dir = tmp_path
    config = ApplicatonConfiguration(command_template=command_template)
    description = build_description(job_dir, payload, config)
    assert description.command == expected
