"""Parses config file as list of applications, schedulers and filesystems."""

from pathlib import Path
from string import Template
from tempfile import gettempdir
from typing import Any

from fastapi import Depends, Request
from pydantic import BaseModel, Field, validator
from pydantic.types import DirectoryPath
from yaml import safe_load as load_yaml

from bartender.destinations import DestinationConfig, default_destinations
from bartender.schedulers.abstract import JobDescription


class ApplicatonConfiguration(BaseModel):
    """Command to run application.

    `$config` in command string will be replaced with value of
    ApplicatonConfiguration.config.

    The config value must be a path relative to the job directory.

    .. code-block:: yaml

        command: wc $config
        config: README.md
    """

    command: str
    config: str
    # TODO make config optional,
    # as some commands don't need a config file name as argument
    allowed_roles: list[str] = []

    def description(self, job_dir: Path) -> JobDescription:
        """Construct job description for this application.

        Args:
            job_dir: In which directory are the input files.

        Returns:
            A job description.
        """
        command = Template(self.command).substitute(
            config=self.config,
        )
        return JobDescription(job_dir=job_dir, command=command)


class Config(BaseModel):
    """Bartender configuration.

    The bartender.settings.Settings class is for FastAPI settings. The
    bartender.config.Config class is for non-FastAPI configuration.

    If config is empty will create a single slot in memory scheduler with a
    local file system.

    """

    applications: dict[str, ApplicatonConfiguration]
    destinations: dict[str, DestinationConfig] = Field(
        default_factory=default_destinations,
    )
    job_root_dir: DirectoryPath = Path(gettempdir()) / "jobs"
    destination_picker: str = "bartender.picker:pick_first"

    class Config:
        validate_all = True

    @validator("applications")
    def applications_non_empty(
        cls,  # noqa: N805 following pydantic docs
        v: dict[str, ApplicatonConfiguration],  # noqa: WPS111 following pydantic docs
    ) -> dict[str, ApplicatonConfiguration]:
        """Validates that applications dict is filled.

        Args:
            v: The given dict.

        Raises:
            ValueError: When dict is empty.

        Returns:
            The given dict.
        """
        if not v:
            raise ValueError("must contain a at least one application")
        return v

    # TODO validate destination_picker
    # check string format
    # optionally check if it can be imported


def build_config(config_filename: Path) -> Config:
    """Build a config instance from a yaml formatted file.

    Args:
        config_filename: File name of configuration file.

    Returns:
        A config instance.
    """
    raw_config = _load(config_filename)
    return Config(**raw_config)


def _load(config_filename: Path) -> Any:
    with open(config_filename) as handle:
        return load_yaml(handle)


def get_config(request: Request) -> Config:
    """Get config based on current request.

    Args:
        request: The current FastAPI request.

    Returns:
        The config.
    """
    return request.app.state.config


def get_roles(config: Config = Depends(get_config)) -> list[str]:
    """Get roles from config.

    Args:
        config: The config.

    Returns:
        list of roles
    """
    roles = []
    for app in config.applications.values():
        for role in app.allowed_roles:
            roles.append(role)
    return roles
