"""Parses config file as list of applications, schedulers and filesystems."""


from pathlib import Path
from tempfile import gettempdir
from typing import Annotated, Any

from fastapi import Depends, Request
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, confloat, root_validator, validator
from pydantic.types import DirectoryPath
from yaml import safe_load as load_yaml

from bartender.destinations import DestinationConfig, default_destinations
from bartender.template_environment import template_environment


class ApplicatonConfiguration(BaseModel):
    """Configuration for an application.

    Attributes:
        command_template: Shell command template to run in job directory.
            Use Jinja2 template syntax to substitute variables from request body.
        input_schema: JSON schema of request body.
            Dialect of JSON Schema should be draft 2020-12.
            Root should be an object.
        summary: The summary of the application, if any.
        description: The description of the application, if any.
        upload_needs: A list of file names that should exist in the
            uploaded archive file during submission.
            If empty then no files are required to be present in the archive.
        allowed_roles: A list of roles that are allowed to submit jobs.
            If empty then anyone can submit jobs.

    Methods:
        check_input_schema(v) -> dict:
            Validate the input schema.

        check_command_template(v) -> str:
            Validate the command template.
    """

    command_template: str
    input_schema: dict[Any, Any] | None = None
    summary: str | None = None
    description: str | None = None
    upload_needs: list[str] = []
    allowed_roles: list[str] = []

    @validator("input_schema")
    def check_input_schema(
        cls,  # noqa: N805
        v: dict[Any, Any] | None,  # noqa: WPS111
    ) -> dict[Any, Any] | None:
        """Validate input schema.

        Args:
            v: The unvalidated input schema.

        Raises:
            ValueError: When input schema is invalid.

        Returns:
            The validated input schema.
        """
        if v is None:
            return v
        Draft202012Validator.check_schema(v)
        if v["type"] != "object":
            raise ValueError("input_schema should have type=object")
        return v

    @validator("command_template")
    def check_command_template(cls, v: str) -> str:  # noqa: N805, WPS111
        """Validate command template.

        Raises TemplateSyntaxError when command template is invalid.

        Args:
            v: The unvalidated command template.

        Returns:
            The validated command template.
        """
        template_environment.from_string(v)
        return v


ApplicatonConfigurations = dict[str, ApplicatonConfiguration]


class InteractiveApplicationConfiguration(BaseModel):
    """Configuration for an interactive application.

    Example:

        Given completed job 1 run interactive app rescore with:

        .. code-block:: python

            response = client.post('/api/job/1/interactiveapp/rescore', json={
                'capri_dir': 'output/06_caprieval',
                'w_elec': 0.2,
                'w_vdw': 0.2,
                'w_desolv': 0.2,
                'w_bsa': 0.1,
                'w_air': 0.3,
            })
            if response.json()['returncode'] == 0:
                # Find the results in the job directory somewhere
                path = '/api/job/1/files/output/06_caprieval_interactive/capri_clt.tsv'
                files = client.get(path)

    Attributes:
        command_template: Shell command template to run in job directory.
            Use Jinja2 template syntax to substitute variables from request body.
        input_schema: JSON schema of request body.
            Dialect of JSON Schema should be draft 2020-12.
            Root should be an object.
        summary: Summary of the interactive app.
        description: Description of the interactive app.
        timeout: Maximum time in seconds to wait for command to finish.
        job_application: Name of the application that generated the job.
            If not set, the interactive app can be run on any job.
            If set, the interactive app can only be run on jobs
            that were submitted for that given application.
    """

    command_template: str
    input_schema: dict[Any, Any]
    summary: str | None = None
    description: str | None = None
    timeout: confloat(gt=0, le=60) = 30.0  # type: ignore
    job_application: str | None = None

    @validator("input_schema")
    def check_input_schema(
        cls,  # noqa: N805
        v: dict[Any, Any],  # noqa: WPS111
    ) -> dict[Any, Any]:
        """Validate input schema.

        Args:
            v: The unvalidated input schema.

        Raises:
            ValueError: When input schema is invalid.

        Returns:
            The validated input schema.
        """
        Draft202012Validator.check_schema(v)
        if v["type"] != "object":
            raise ValueError("input_schema should have type=object")
        return v

    @validator("command_template")
    def check_command_template(cls, v: str) -> str:  # noqa: N805, WPS111
        """Validate command template.

        Raises TemplateSyntaxError when command template is invalid.

        Args:
            v: The unvalidated command template.

        Returns:
            The validated command template.
        """
        template_environment.from_string(v)
        return v


InteractiveApplicationConfigurations = dict[str, InteractiveApplicationConfiguration]


class Config(BaseModel):
    """Bartender configuration.

    The bartender.settings.Settings class is for FastAPI settings. The
    bartender.config.Config class is for non-FastAPI configuration.

    If config is empty will create a single slot in memory scheduler with a
    local file system.

    """

    applications: ApplicatonConfigurations
    destinations: dict[str, DestinationConfig] = Field(
        default_factory=default_destinations,
    )
    job_root_dir: DirectoryPath = Path(gettempdir()) / "jobs"
    destination_picker: str = "bartender.picker:pick_first"
    interactive_applications: InteractiveApplicationConfigurations = {}

    class Config:
        validate_all = True

    @validator("applications")
    def applications_non_empty(
        cls,  # noqa: N805 following pydantic docs
        v: ApplicatonConfigurations,  # noqa: WPS111 following pydantic docs
    ) -> ApplicatonConfigurations:
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

    @root_validator
    def check_job_application(
        cls,  # noqa: N805 following pydantic docs
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Check that all interactive applications have a valid job_application.

        Args:
            values: The configuration values to check.

        Returns:
            The original configuration values.

        Raises:
            AssertionError: If an interactive application has
                an invalid job_application.
        """
        if "applications" not in values or "interactive_applications" not in values:
            return values
        valid_applications = set(values["applications"].keys())
        for name, config in values["interactive_applications"].items():
            if config.job_application is None:
                continue
            assert (  # noqa: S101
                config.job_application in valid_applications
            ), f"Interactive application {name} has invalid job_application {config.job_application}"  # noqa: E501
        return values


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
