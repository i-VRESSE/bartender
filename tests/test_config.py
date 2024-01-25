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
from bartender.schedulers.memory import MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmSchedulerConfig
from bartender.shared.ssh import SshConnectConfig


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
            "applications": {"app1": {"command_template": "uptime"}},
        }
        config = Config(**raw_config)

        expected = Config(
            destination_picker="bartender.picker:pick_first",
            job_root_dir=tmp_path,
            applications={
                "app1": ApplicatonConfiguration(command_template="uptime"),
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
            "applications": {"app1": {"command_template": "uptime"}},
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
                "app1": ApplicatonConfiguration(command_template="uptime"),
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

    def test_job_application_valid(self, tmp_path: Path) -> None:
        raw_config: Any = {
            "job_root_dir": str(tmp_path),
            "applications": {"app1": {"command_template": "uptime"}},
            "interactive_applications": {
                "app2": {
                    "command_template": "hostname",
                    "input_schema": {"type": "object"},
                    "job_application": "app1",
                },
                "app3": {
                    "command_template": "hostname",
                    "input_schema": {"type": "object"},
                    # Absent is valid
                },
            },
        }
        config = Config(**raw_config)
        assert config.interactive_applications["app2"].job_application == "app1"

    def test_job_application_invalid(self, tmp_path: Path) -> None:
        config: Any = {
            "job_root_dir": str(tmp_path),
            "applications": {"app1": {"command_template": "uptime"}},
            "interactive_applications": {
                "app2": {
                    "command_template": "hostname",
                    "input_schema": {"type": "object"},
                    "job_application": "app99",
                },
            },
        }
        with pytest.raises(
            ValidationError,
            match="Interactive application app2 has invalid job_application app99",
        ):
            Config(**config)

    def test_check_input_schema_valid_schema(self) -> None:
        input_schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
        config = ApplicatonConfiguration(
            command_template="echo {{ message }}",
            input_schema=input_schema,
        )
        assert config.input_schema == input_schema

    def test_check_input_schema_invalid_schema(self) -> None:
        input_schema = {"type": "incorrect"}
        with pytest.raises(
            SchemaError,
            match="is not valid under any of the given schemas",
        ):
            ApplicatonConfiguration(
                command_template="hostname",
                input_schema=input_schema,
            )

    def test_check_input_schema_not_a_object(self) -> None:
        input_schema = {"type": "string"}
        with pytest.raises(ValueError, match="input_schema should have type=object"):
            ApplicatonConfiguration(
                command_template="hostname",
                input_schema=input_schema,
            )


@pytest.mark.anyio
async def test_build_config_minimal(tmp_path: Path) -> None:
    file = tmp_path / "config.yaml"
    config: Any = {
        "job_root_dir": str(tmp_path),
        "applications": {"app1": {"command_template": "uptime"}},
    }
    with file.open("w") as handle:
        yaml_dump(config, handle)

    result = build_config(file)

    expected = Config(
        destination_picker="bartender.picker:pick_first",
        job_root_dir=tmp_path,
        applications={
            "app1": ApplicatonConfiguration(command_template="uptime"),
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
    def test_check_input_schema_valid_schema(self) -> None:
        input_schema = {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        }
        config = InteractiveApplicationConfiguration(
            command_template="echo {{ message }}",
            input_schema=input_schema,
        )
        assert config.input_schema == input_schema

    def test_check_input_schema_invalid_schema(self) -> None:
        input_schema = {"type": "incorrect"}
        with pytest.raises(
            SchemaError,
            match="is not valid under any of the given schemas",
        ):
            InteractiveApplicationConfiguration(
                command_template="hostname",
                input_schema=input_schema,
            )

    def test_check_input_schema_not_a_object(self) -> None:
        input_schema = {"type": "string"}
        with pytest.raises(ValueError, match="input_schema should have type=object"):
            InteractiveApplicationConfiguration(
                command_template="hostname",
                input_schema=input_schema,
            )

    def test_check_command_template_valid_jinja(self) -> None:
        command_template = "echo {{ message }}"
        input_schema = {"type": "object"}
        config = InteractiveApplicationConfiguration(
            command_template=command_template,
            input_schema=input_schema,
        )
        assert config.command_template == command_template

    def test_check_command_template_invalid_jinja(self) -> None:
        command_template = "echo {{ message"
        input_schema = {"type": "object"}
        with pytest.raises(TemplateSyntaxError, match="unexpected end of template"):
            InteractiveApplicationConfiguration(
                command_template=command_template,
                input_schema=input_schema,
            )
