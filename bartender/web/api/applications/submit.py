from pathlib import Path

from bartender.context import Context
from bartender.db.dao.job_dao import JobDAO
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription


async def submit(
    external_job_id: int,
    job_dir: Path,
    application: str,
    job_dao: JobDAO,
    context: Context,
) -> None:
    """Submit job description to scheduler and store job id returned by scheduler in db.

    :param external_job_id: External job id.
    :param job_dir: Location where job input files are located.
    :param application: Application name that should be run.
    :param job_dao: JobDAO object.
    :param context: Context with applications and destinations.
    """
    application_config = context.applications[application]
    description = application_config.description(job_dir)

    destination_name = context.destination_picker(
        job_dir,
        application,
        context,
    )
    destination = context.destinations[destination_name]

    await _upload_input_files(description, destination.filesystem, context.job_root_dir)

    internal_job_id = await destination.scheduler.submit(description)

    await job_dao.update_internal_job_id(
        external_job_id,
        internal_job_id,
        destination_name,
    )


async def _upload_input_files(
    description: JobDescription,
    filesystem: AbstractFileSystem,
    job_root_dir: Path,
) -> None:
    localized_description = filesystem.localize_description(
        description,
        job_root_dir,
    )
    await filesystem.upload(
        src=description,
        target=localized_description,
    )
