from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import CompletedStates, Job, State
from bartender.destinations import Destination
from bartender.filesystems.queue import FileStagingQueue


async def sync_state(
    job: Job,
    job_dao: JobDAO,
    destination: Destination,
    file_staging_queue: FileStagingQueue,
) -> None:
    """Sync state of job from scheduler to database.

    When job is completed then downloading of the output will be queued.

    Args:
        job: Job instance.
        job_dao: JobDAO object.
        destination: Job destination used to submit job.
        file_staging_queue: When scheduler reports job is complete.
            The output files need to be copied back.
            Use queue to perform download outside request/response handling.
    """
    if job.state not in CompletedStates and job.internal_id is not None:
        state = await destination.scheduler.state(job.internal_id)
        await update_state_and_stage_out(
            job_dao,
            file_staging_queue,
            job,
            state,
        )


async def update_state_and_stage_out(
    job_dao: JobDAO,
    file_staging_queue: FileStagingQueue,
    job: Job,
    state: State,
) -> None:
    """Update state of job and when completed then queue the staging out of its files.

    Args:
        job_dao: Object to update jobs in database.
        file_staging_queue: Queue used to defer downloading.
        job: Job for which new state should be set.
        state: The new state, most likely retrieved from a
            scheduler.
    """
    if job.state != state and job.id is not None and job.state != "staging_out":
        if state in CompletedStates and job.destination:
            # when scheduler says job is completed then download output files
            await job_dao.update_job_state(job.id, "staging_out")
            await file_staging_queue.put((job.id, job.destination, state))
            # once download is complete the state in db will be updated by queue worker.
        else:
            await job_dao.update_job_state(job.id, state)
            job.state = state


async def sync_states(
    jobs: list[Job],
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    file_staging_queue: FileStagingQueue,
) -> None:
    """Sync state of jobs from scheduler to database.

    Args:
        jobs: Job instances.
        destinations: Job destinations.
        job_dao: JobDAO object.
        file_staging_queue: When scheduler reports job is complete.
            The output files need to be copied back.
            Use queue to perform download outside request/response handling.
    """
    jobs2sync = [
        job
        for job in jobs
        if job.state not in CompletedStates and job.state != "staging_out"
    ]
    states = await _states_of_destinations(destinations, jobs2sync)
    for job in jobs2sync:
        if job.id is None or job.destination is None:
            continue  # mypy type narrowing, should never get here
        await update_state_and_stage_out(
            job_dao,
            file_staging_queue,
            job,
            states[job.id],
        )


async def _states_of_destinations(
    destinations: dict[str, Destination],
    jobs2sync: list[Job],
) -> dict[int, State]:
    states: dict[int, State] = {}
    for destination_name, destination in destinations.items():
        dest_states = await _states_of_destination(
            jobs2sync,
            destination_name,
            destination,
        )
        states.update(dest_states)
    return states


async def _states_of_destination(
    jobs2sync: list[Job],
    destination_name: str,
    destination: Destination,
) -> dict[int, State]:
    dest_states: dict[int, State] = {}
    # List of External job id and internal job id pairs
    job_ids: list[tuple[int, str]] = [
        (job.id, job.internal_id)
        for job in jobs2sync
        if job.id is not None
        and job.internal_id is not None
        and job.destination == destination_name
    ]
    if job_ids:
        scheduler_states = await destination.scheduler.states(
            [job_id[1] for job_id in job_ids],
        )
        for index, job_id in enumerate(job_ids):
            dest_states[job_id[0]] = scheduler_states[index]
    return dest_states
