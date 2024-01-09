"""Parses config file as list of applications, schedulers and filesystems."""

from pathlib import Path
from string import Template
from tempfile import gettempdir
from typing import Annotated, Any

from fastapi import Depends, Request
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, confloat, root_validator, validator
from pydantic.types import DirectoryPath
from yaml import safe_load as load_yaml

from bartender.destinations import DestinationConfig, default_destinations
from bartender.schedulers.abstract import JobDescription
from bartender.template_environment import template_environment


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
            raise ValueError("input should have type=object")
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


def unroll_application_routes(
    openapi_schema: dict[str, Any],
    applications: ApplicatonConfigurations,
) -> None:
    """Unroll application routes.

    Replaces `/api/application/{application}` endpoints.
    Loops over config.applications and add a post route for each

    Args:
        openapi_schema: OpenAPI schema
        applications: Application configurations
    """
    existing_put_path = openapi_schema["paths"].pop(
        "/api/application/{application}",
    )["put"]

    for aname, config in applications.items():
        # each application has different request due to config file
        # so instead of reusing the same schema for all applications
        # we need to generate a new one for each application
        openapi_schema["paths"][f"/api/application/{aname}"] = {
            "put": unroll_application_route(aname, config, existing_put_path),
        }

    # Drop schema for /api/application/{application} put request
    ref = existing_put_path["requestBody"]["content"][  # noqa: WPS219
        "multipart/form-data"
    ]["schema"]["$ref"]
    del openapi_schema["components"]["schemas"][  # noqa: WPS420
        ref.replace("#/components/schemas/", "")
    ]


def unroll_application_route(
    aname: str,
    config: ApplicatonConfiguration,
    existing_put_path: Any,
) -> dict[str, Any]:
    """Unroll application route.

    Args:
        aname: Application name
        config: Application configuration
        existing_put_path: Existing PUT path

    Returns:
        Unrolled PUT path
    """
    desc = f"Archive containing {config.config} file."
    request_body = {
        "content": {
            "multipart/form-data": {
                "schema": {
                    "properties": {
                        "upload": {
                            "type": "string",
                            "format": "binary",
                            "title": "Upload",
                            "description": desc,
                        },
                    },
                    "type": "object",
                    "required": ["upload"],
                    "title": f"Upload {aname}",
                },
                # Enfore uploaded file is a certain content type
                # See https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.0.3.md#encoding-object  # noqa: E501
                # does not seem supported by Swagger UI or FastAPI
                "encoding": {
                    "upload": {
                        "contentType": "application/zip",
                    },
                },
            },
        },
        "required": True,
    }
    return {
        "tags": ["application"],
        "operationId": f"upload_{aname}",
        "summary": f"Upload job to {aname}",
        "requestBody": request_body,
        "responses": existing_put_path["responses"],
        "security": existing_put_path["security"],
    }


def unroll_interactive_app_routes(
    openapi_schema: dict[str, Any],
    interactive_applications: InteractiveApplicationConfigurations,
) -> None:
    """Unroll interactive app routes.

    Replaces `/api/job/{jobid}/interactive/{application}` endpoint.
    Loops over config.interactive_applications and add a post route for each

    Args:
        openapi_schema: OpenAPI schema
        interactive_applications: Interactive application configurations
    """
    path = "/api/job/{jobid}/interactive/{application}"
    existing_post_path = openapi_schema["paths"].pop(path)["post"]
    for iname, config in interactive_applications.items():
        path = f"/api/job/{{jobid}}/interactive/{iname}"
        post = {
            "tags": ["interactive"],
            "operationId": iname,
            "parameters": [
                {
                    "name": "jobid",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                },
            ],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": config.input_schema,
                    },
                },
            },
            "responses": existing_post_path["responses"],
            "security": existing_post_path["security"],
        }
        if config.summary is not None:
            post["summary"] = config.summary
        else:
            post["summary"] = f"Run {iname} interactive application"
        if config.description is not None:
            post["description"] = config.description
        openapi_schema["paths"][path] = {"post": post}
