from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from jinja2.exceptions import TemplateSyntaxError
from jsonschema import SchemaError
from pydantic import ValidationError
from yaml import safe_dump as yaml_dump

from bartender.config import (
    ApplicatonConfiguration,
    Config,
    InteractiveApplicationConfiguration,
    build_config,
    get_config,
)
from bartender.destinations import DestinationConfig
from bartender.filesystems.local import LocalFileSystemConfig
from bartender.filesystems.sftp import SftpFileSystemConfig
from bartender.schedulers.abstract import JobDescription
from bartender.schedulers.memory import MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmSchedulerConfig
from bartender.shared.ssh import SshConnectConfig


class TestApplicatonConfiguration:
    def test_description_with_config(self, tmp_path: Path) -> None:
        conf = ApplicatonConfiguration(command="wc $config", config="foo.bar")

        description = conf.description(tmp_path)

        expected = JobDescription(job_dir=tmp_path, command="wc foo.bar")
        assert description == expected


class TestConfig:
    def test_zero_apps(self) -> None:
        raw_config: Any = {"applications": {}}
        with pytest.raises(
            ValidationError,
            match="must contain a at least one application",
        ):
            Config(**raw_config)

    def test_minimal(self, tmp_path: Path) -> None:
        raw_config: Any = {
            "job_root_dir": str(tmp_path),
            "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
        }
        config = Config(**raw_config)

        expected = Config(
            destination_picker="bartender.picker:pick_first",
            job_root_dir=tmp_path,
            applications={
                "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
            },
            destinations={
                "": DestinationConfig(
                    scheduler=MemorySchedulerConfig(),
                    filesystem=LocalFileSystemConfig(),
                ),
            },
        )
        assert config == expected

    def test_no_defaults(self, tmp_path: Path) -> None:
        raw_config: Any = {
            "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
            "destinations": {
                "dest1": {
                    "scheduler": {"type": "slurm", "partition": "normal"},
                    "filesystem": {
                        "type": "sftp",
                        "entry": "/scratch",
                        "ssh_config": {"hostname": "remotehost"},
                    },
                },
            },
            "job_root_dir": str(tmp_path),
            "destination_picker": "bartender.picker:pick_round",
        }
        config = Config(**raw_config)

        expected = Config(
            destination_picker="bartender.picker:pick_round",
            job_root_dir=tmp_path,
            applications={
                "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
            },
            destinations={
                "dest1": DestinationConfig(
                    scheduler=SlurmSchedulerConfig(partition="normal"),
                    filesystem=SftpFileSystemConfig(
                        entry=Path("/scratch"),
                        ssh_config=SshConnectConfig(hostname="remotehost"),
                    ),
                ),
            },
        )
        assert config == expected


@pytest.mark.anyio
async def test_build_config_minimal(tmp_path: Path) -> None:
    file = tmp_path / "config.yaml"
    config: Any = {
        "job_root_dir": str(tmp_path),
        "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
    }
    with file.open("w") as handle:
        yaml_dump(config, handle)

    result = build_config(file)

    expected = Config(
        destination_picker="bartender.picker:pick_first",
        job_root_dir=tmp_path,
        applications={
            "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
        },
        destinations={
            "": DestinationConfig(
                scheduler=MemorySchedulerConfig(),
                filesystem=LocalFileSystemConfig(),
            ),
        },
    )
    assert result == expected


def test_get_config(demo_config: Config) -> None:
    fake_request = MagicMock()
    fake_request.app.state.config = demo_config

    config = get_config(fake_request)

    expected = demo_config
    assert config == expected


class TestInteractiveApplicationConfiguration:
    def test_check_input_valid_schema(self) -> None:
        input_schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
        config = InteractiveApplicationConfiguration(
            command="echo {{ message }}",
            input=input_schema,
        )
        assert config.input == input_schema

    def test_check_input_invalid_schema(self) -> None:
        input_schema = {"type": "incorrect"}
        with pytest.raises(
            SchemaError,
            match="is not valid under any of the given schemas",
        ):
            InteractiveApplicationConfiguration(command="hostname", input=input_schema)

    def test_check_input_not_a_object(self) -> None:
        input_schema = {"type": "string"}
        with pytest.raises(ValueError, match="input should have type=object"):
            InteractiveApplicationConfiguration(command="hostname", input=input_schema)

    def test_check_command_valid_jinja(self) -> None:
        command = "echo {{ message }}"
        input_schema = {"type": "object"}
        config = InteractiveApplicationConfiguration(
            command=command,
            input=input_schema,
        )
        assert config.command == command

    def test_check_command_invalid_jinja(self) -> None:
        command = "echo {{ message"
        input_schema = {"type": "object"}
        with pytest.raises(TemplateSyntaxError, match="unexpected end of template"):
            InteractiveApplicationConfiguration(command=command, input=input_schema)
