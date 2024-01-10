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
    unroll_application_routes,
    unroll_interactive_app_routes,
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

    def test_job_application_valid(self, tmp_path: Path) -> None:
        raw_config: Any = {
            "job_root_dir": str(tmp_path),
            "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
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
            "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
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


def test_unroll_application_routes() -> None:
    openapi_schema = {
        "paths": {
            "/api/application/{application}": {
                "put": {
                    "responses": "mock responses",
                    "security": "mock security",
                    "requestBody": {
                        "content": {
                            "multipart/form-data": {
                                "schema": {
                                    "$ref": "#/components/schemas/JobDescription",
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "JobDescription": "mock JobDescription",
            },
        },
    }
    applications = {
        "app1": ApplicatonConfiguration(command="echo", config="somefile"),
    }

    unroll_application_routes(openapi_schema, applications)

    expected_request_body = {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "properties": {
                        "upload": {
                            "type": "string",
                            "format": "binary",
                            "title": "Upload",
                            "description": "Archive containing somefile file.",
                        },
                    },
                    "type": "object",
                    "required": ["upload"],
                    "title": "Upload app1",
                },
                "encoding": {
                    "upload": {
                        "contentType": "application/zip, application/x-zip-compressed",
                    },
                },
            },
        },
        "required": True,
    }
    expected = {
        "paths": {
            "/api/application/app1": {
                "put": {
                    "tags": ["application"],
                    "operationId": "application_app1",
                    "summary": "Upload job to app1",
                    "requestBody": expected_request_body,
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
        "components": {
            "schemas": {},
        },
    }
    assert openapi_schema == expected


def test_unroll_interactive_app_routes() -> None:
    openapi_schema = {
        "paths": {
            "/api/job/{jobid}/interactive/{application}": {
                "post": {
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
    }
    input_schema = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    interactive_applications = {
        "iapp1": InteractiveApplicationConfiguration(
            command_template="echo {{ message }}",
            input_schema=input_schema,
        ),
    }

    unroll_interactive_app_routes(openapi_schema, interactive_applications)

    expected = {
        "paths": {
            "/api/job/{jobid}/interactive/iapp1": {
                "post": {
                    "tags": ["interactive"],
                    "operationId": "interactive_application_iapp1",
                    "summary": "Run iapp1 interactive application",
                    "parameters": [
                        {
                            "name": "jobid",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "number"},
                        },
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": input_schema,
                            },
                        },
                    },
                    "responses": "mock responses",
                    "security": "mock security",
                },
            },
        },
    }
    assert openapi_schema == expected
