from pathlib import Path

from bartender.config import Config
from bartender.db.dao.job_dao import JobDAO
from bartender.destinations import Destination
from bartender.schedulers.abstract import JobDescription


async def submit(
    external_job_id: int,
    job_dir: Path,
    application: str,
    job_dao: JobDAO,
    config: Config,
) -> None:
    """Submit job description to scheduler and store job id returned by scheduler in db.

    :param external_job_id: External job id.
    :param job_dir: Location where job input files are located.
    :param application: Application name that should be run.
    :param job_dao: JobDAO object.
    :param config: Config with applications and destinations.
    """
    application_config = config.applications[application]
    description = application_config.description(job_dir)

    destination, destinations_name = config.destination_picker(
        job_dir,
        application,
        config,
    )

    await _upload_input_files(description, destination, config.job_root_dir)

    internal_job_id = await destination.scheduler.submit(description)

    await job_dao.update_internal_job_id(
        external_job_id,
        internal_job_id,
        destinations_name,
    )


async def _upload_input_files(
    description: JobDescription,
    destination: Destination,
    job_root_dir: Path,
) -> None:
    localized_description = destination.filesystem.localize_description(
        description,
        job_root_dir,
    )
    await destination.filesystem.upload(
        src=description,
        target=localized_description,
    )
