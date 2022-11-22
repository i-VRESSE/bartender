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

    destination, destinations_name = pick_destination(job_dir, application, config)

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


def pick_destination(
    job_dir: Path,
    application_name: str,
    config: Config,
) -> tuple[Destination, str]:
    """Pick to which destination a job should be submitted.

    :param job_dir: Location where job input files are located.
    :param application_name: Application name that should be run.
    :param config: Config with applications and destinations.
    :return: Destination where job should be submitted to.
    """
    # TODO allow maintaner of service to provide Python function that
    # returns the destination for this job
    # for now the first destination in the configuration is picked.
    destination_names = list(config.destinations.keys())
    destination_name = destination_names[0]
    destination = config.destinations[destination_name]
    return destination, destination_name
