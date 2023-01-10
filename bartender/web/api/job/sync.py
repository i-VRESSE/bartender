from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import CompletedStates, Job
from bartender.schedulers.abstract import AbstractScheduler


async def sync_state(job: Job, job_dao: JobDAO, scheduler: AbstractScheduler) -> None:
    """Sync state of job from scheduler to database.

    :param job: Job instance.
    :param job_dao: JobDAO object.
    :param scheduler: Current job scheduler.
    """
    if job.state not in CompletedStates and job.internal_id is not None:
        # TODO throttle getting state from scheduler as getting state could be expensive
        # could add column to Job to track when state was last fetched
        state = await scheduler.state(job.internal_id)
        if job.state != state and job.id is not None:
            await job_dao.update_job_state(job.id, state)
            job.state = state


async def sync_states(
    jobs: list[Job],
    scheduler: AbstractScheduler,
    job_dao: JobDAO,
) -> None:
    """Sync state of jobs from scheduler to database.

    :param jobs: Job instances.
    :param job_dao: JobDAO object.
    :param scheduler: Current job scheduler.
    """
    jobs2sync = [
        job
        for job in jobs
        if job.state not in CompletedStates and job.internal_id is not None
    ]
    states = await scheduler.states(
        [job.internal_id for job in jobs2sync if job.internal_id is not None],
    )
    for job, state in zip(jobs2sync, states):
        if job.state != state and job.id is not None:
            await job_dao.update_job_state(job.id, state)
            job.state = state
