"""Parses config file as list of applications, schedulers and filesystems."""

from pathlib import Path
from string import Template
from tempfile import gettempdir
from typing import Annotated, Any

from fastapi import Depends, Request
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, confloat, validator
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


class InteractiveApplicationConfiguration(BaseModel):
    """Configuration for an interactive application.

    Interactive apps that can be run on a completed job.

    Interactive apps are small interactive calculations that
    can be run within a request-response cycle (<30s).

    A interactive app should

    * be quick to run (<60s)
    * produce very little output (stdout, stderr, files)
    * in the job directory only write new files and overwrite its own files.
    * not have any arguments that can leak information,
        for example paths to files outside the job directory.

    Example:

        Given completed job 123 run interactive app rescore with:

        ```python
        response = client.post('/api/job/123/interactiveapp/rescore', json={
            'module': 1,
            'w_elec': 0.2,
            'w_vdw': 0.2,
            'w_desolv': 0.2,
            'w_bsa': 0.1,
            'w_air': 0.3,
        })
        if response.json()['returncode'] == 0:
            # Find the results in the job directory somewhere
            files = client.get('/api/job/123/files')
        ```

    Attributes:
        command: Shell command template to run in job directory.
            Use Python string template syntax to substitute variables from request body.
        input: JSON schema of request body.
            Dialect of JSON Schema should be draft 2020-12.
            Root should be an object and its properties should be scalar.
        description: Description of the interactive app.
        timeout: Maximum time in seconds to wait for command to finish.
    """

    command: str
    input: dict[Any, Any]
    description: str = ""
    timeout: confloat(gt=0, le=60) = 30.0

    @validator("input")
    def check_input(cls, v):
        """Validate input schema.

        Args:
            v: The unvalidated input schema.

        Raises:
            ValueError: When input schema is invalid.
        """
        Draft202012Validator.check_schema(v)
        if v["type"] != "object":
            raise ValueError("input should have type=object")
        if "properties" in v:
            for prop in v["properties"].values():
                # TODO add enum support aka {"enum": ["red", "amber", "green"]}
                if prop["type"] not in {"string", "integer", "number", "boolean"}:
                    raise ValueError(
                        "input properties be scalar",
                    )
        return v


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
    interactive_applications: dict[str, InteractiveApplicationConfiguration] = {}

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


CurrentConfig = Annotated[Config, Depends(get_config)]


def get_roles(config: CurrentConfig) -> list[str]:
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


CurrentRoles = Annotated[list[str], Depends(get_roles)]
