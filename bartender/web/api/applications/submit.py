from pathlib import Path
from string import Template

from bartender.config import ApplicatonConfiguration, Config
from bartender.db.dao.job_dao import JobDAO
from bartender.destinations import Destination
from bartender.schedulers.abstract import JobDescription
from bartender.settings import settings


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
    description = _build_description(job_dir, application_config)

    destination, destinations_name = pick_destination(job_dir, application, config)

    await _upload_input_files(description, destination)

    internal_job_id = await destination.scheduler.submit(description)

    await job_dao.update_internal_job_id(
        external_job_id,
        internal_job_id,
        destinations_name,
    )


async def _upload_input_files(
    description: JobDescription,
    destination: Destination,
) -> None:
    if destination.filesystem is not None:
        localized_description = destination.filesystem.localize_description(
            description,
            settings.job_root_dir,
        )
        await destination.filesystem.upload(
            src=description,
            target=localized_description,
        )


def _build_description(
    job_dir: Path,
    application_config: ApplicatonConfiguration,
) -> JobDescription:
    command = Template(application_config.command).substitute(
        config=application_config.config,
    )
    return JobDescription(job_dir=job_dir, command=command)


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
