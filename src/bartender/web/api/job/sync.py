from pathlib import Path

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import CompletedStates, Job, State
from bartender.destinations import Destination
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription


async def sync_state(
    job: Job,
    job_dao: JobDAO,
    destination: Destination,
    job_root_dir: Path,
) -> None:
    """Sync state of job from scheduler to database.

    Args:
        job: Job instance.
        job_dao: JobDAO object.
        destination: Job destination used to submit job.
        job_root_dir: Directory where all jobs can be found.
    """
    if (  # noqa: WPS337
        job.state not in CompletedStates
        and job.internal_id is not None
        and destination is not None
    ):
        # TODO throttle getting state from scheduler as getting state could be expensive
        # could add column to Job to track when state was last fetched
        state = await destination.scheduler.state(job.internal_id)
        # when scheduler says job is completed then download output files
        if job.state != state and job.id is not None:
            await _download_job_files(job, state, destination.filesystem, job_root_dir)
            await job_dao.update_job_state(job.id, state)
            job.state = state


async def sync_states(
    jobs: list[Job],
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    job_root_dir: Path,
) -> None:
    """Sync state of jobs from scheduler to database.

    Args:
        jobs: Job instances.
        destinations: Job destinations.
        job_dao: JobDAO object.
        job_root_dir: Directory where all jobs can be found.
    """
    jobs2sync = [
        job
        for job in jobs
        if job.id is not None
        and job.state not in CompletedStates
        and job.internal_id is not None
    ]
    states = await _states_of_destinations(destinations, jobs2sync)
    for job in jobs2sync:
        await _store_updated_state(destinations, job_dao, states, job, job_root_dir)


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


async def _store_updated_state(
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    states: dict[int, State],
    job: Job,
    job_root_dir: Path,
) -> None:
    if job.id is not None:
        state = states[job.id]
        if job.state != state and job.destination is not None:
            filesystem = destinations[job.destination].filesystem
            await _download_job_files(job, state, filesystem, job_root_dir)
            await job_dao.update_job_state(job.id, state)
            job.state = state


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


async def _download_job_files(
    job: Job,
    state: State,
    filesystem: AbstractFileSystem,
    job_root_dir: Path,
) -> None:
    if state in CompletedStates:
        job_dir: Path = job_root_dir / str(job.id)
        # Command does not matter for downloading so use dummy command.
        description = JobDescription(job_dir=job_dir, command="echo")
        localized_description = filesystem.localize_description(
            description,
            job_root_dir,
        )
        await filesystem.download(localized_description, description)
        # TODO for non-local file system should also remove remote files?
