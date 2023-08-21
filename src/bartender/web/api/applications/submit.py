from pathlib import Path

from bartender.context import Context
from bartender.db.dao.job_dao import JobDAO
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription
from bartender.web.users import User


async def submit(  # noqa: WPS211
    external_job_id: int,
    job_dir: Path,
    application: str,
    submitter: User,
    job_dao: JobDAO,
    context: Context,
) -> None:
    """Submit job description to scheduler and store job id returned by scheduler in db.

    Args:
        external_job_id: External job id.
        job_dir: Location where job input files are located.
        application: Application name that should be run.
        submitter: User that submitted the job.
        job_dao: JobDAO object.
        context: Context with applications and destinations.
    """
    description = context.applications[application].description(job_dir)

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
