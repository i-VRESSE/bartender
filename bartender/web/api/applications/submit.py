from pathlib import Path
from string import Template

from bartender.db.dao.job_dao import JobDAO
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.settings import AppSetting


# TODO submit function should be an adapter,
# which can submit job to one of the available schedulers
# based on job input, application, scheduler resources, phase of moon, etc.
async def submit(
    external_job_id: int,
    job_dir: Path,
    application: AppSetting,
    job_dao: JobDAO,
    scheduler: AbstractScheduler,
) -> None:
    """Submit job description to scheduler and store job id returned by scheduler in db.

    :param external_job_id: External job id.
    :param job_dir: Location where job input files are located.
    :param application: Application that should be run.
    :param job_dao: JobDAO object.
    :param scheduler: Current job scheduler.
    """
    command = Template(application.command).substitute(config=application.config)
    description = JobDescription(job_dir=job_dir, command=command)
    # TODO if scheduler has filesystem then perform upload
    # of job dir and localize description
    internal_job_id = await scheduler.submit(description)
    await job_dao.update_internal_job_id(external_job_id, internal_job_id)
