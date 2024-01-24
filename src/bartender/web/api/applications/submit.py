from pathlib import Path

from jsonschema import Draft202012Validator

from bartender.config import ApplicatonConfiguration
from bartender.context import Context
from bartender.db.dao.job_dao import JobDAO
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription
from bartender.template_environment import template_environment
from bartender.web.users import User


def build_description(
    job_dir: Path,
    payload: dict[str, str],
    config: ApplicatonConfiguration,
) -> JobDescription:
    """
    Builds a job description.

    Args:
        job_dir: The directory where the job will be executed.
        payload: The payload containing the non-file input data for the job.
        config: The configuration for the application.

    Returns:
        Job description containing the job directory and command.
    """
    if config.input_schema is not None:
        validator = Draft202012Validator(config.input_schema)
        # payload values are strings, while the input_schema might expect other types
        # TODO convert strings to numbers or booleans where needed.
        # use https://jschon.readthedocs.io evaluate().output()?
        # now throws an error if schema expects non-string
        validator.validate(payload)

    template = template_environment.from_string(config.command_template)
    render_args = {**payload, **config.upload_needs}
    command = template.render(**render_args)
    return JobDescription(job_dir=job_dir, command=command)


async def submit(  # noqa: WPS211
    external_job_id: int,
    job_dir: Path,
    application: str,
    submitter: User,
    payload: dict[str, str],
    job_dao: JobDAO,
    context: Context,
) -> None:
    """Submit job description to scheduler and store job id returned by scheduler in db.

    Args:
        external_job_id: External job id.
        job_dir: Location where job input files are located.
        application: Application name that should be run.
        submitter: User that submitted the job.
        payload: Payload with non-file input data.
        job_dao: JobDAO object.
        context: Context with applications and destinations.
    """
    description = build_description(job_dir, payload, context.applications[application])

    destination_name = context.destination_picker(
        job_dir,
        application,
        submitter,
        context,
    )
    destination = context.destinations[destination_name]

    localized_description = destination.filesystem.localize_description(
        description,
        context.job_root_dir,
    )

    await _upload_input_files(
        description,
        destination.filesystem,
        localized_description,
    )

    internal_job_id = await destination.scheduler.submit(localized_description)

    await job_dao.update_internal_job_id(
        external_job_id,
        internal_job_id,
        destination_name,
    )


async def _upload_input_files(
    description: JobDescription,
    filesystem: AbstractFileSystem,
    localized_description: JobDescription,
) -> None:
    await filesystem.upload(
        src=description,
        target=localized_description,
    )
