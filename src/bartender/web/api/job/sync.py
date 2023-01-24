from pathlib import Path
from typing import Any, Callable, Coroutine

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import CompletedStates, Job, State
from bartender.destinations import Destination
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.queue import FileStagingQueue
from bartender.schedulers.abstract import JobDescription


async def sync_state(
    job: Job,
    job_dao: JobDAO,
    destination: Destination,
    job_root_dir: Path,
    file_staging_queue: FileStagingQueue,
) -> None:
    """Sync state of job from scheduler to database.

    :param job: Job instance.
    :param job_dao: JobDAO object.
    :param destination: Job destination used to submit job.
    :param job_root_dir: Directory where all jobs can be found.
    :param file_staging_queue: When scheduler reports job is complete.
        The output files need to be copied back.
        Use queue to perform download outside request/response handling.
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
            if state in CompletedStates:
                await job_dao.update_job_state(job.id, "staging_out")
                perform_download = _download_job_files(
                    job,
                    job_dao,
                    state,
                    destination.filesystem,
                    job_root_dir,
                )
                await file_staging_queue.put(perform_download)
            else:
                await job_dao.update_job_state(job.id, state)
                job.state = state


async def sync_states(
    jobs: list[Job],
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    job_root_dir: Path,
    file_staging_queue: FileStagingQueue,
) -> None:
    """Sync state of jobs from scheduler to database.

    :param jobs: Job instances.
    :param destinations: Job destinations.
    :param job_dao: JobDAO object.
    :param job_root_dir: Directory where all jobs can be found.
    :param file_staging_queue: When scheduler reports job is complete.
        The output files need to be copied back.
        Use queue to perform download outside request/response handling.
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
        await _store_updated_state(
            destinations,
            job_dao,
            states,
            job,
            job_root_dir,
            file_staging_queue,
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


async def _store_updated_state(  # noqa: WPS211
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    states: dict[int, State],
    job: Job,
    job_root_dir: Path,
    file_staging_queue: FileStagingQueue,
) -> None:
    if job.id is not None:
        state = states[job.id]
        if job.state != state and job.destination is not None:
            filesystem = destinations[job.destination].filesystem
            if state in CompletedStates:
                await job_dao.update_job_state(job.id, "staging_out")
                perform_download = _download_job_files(
                    job,
                    job_dao,
                    state,
                    filesystem,
                    job_root_dir,
                )
                await file_staging_queue.put(perform_download)
            else:
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


def _download_job_files(
    job: Job,
    job_dao: JobDAO,
    state: State,
    filesystem: AbstractFileSystem,
    job_root_dir: Path,
) -> Callable[[], Coroutine[Any, Any, None]]:
    async def perform_download() -> None:  # noqa: WPS430 queue.put gets function
        job_dir: Path = job_root_dir / str(job.id)
        # Command does not matter for downloading so use dummy command.
        description = JobDescription(job_dir=job_dir, command="echo")
        localized_description = filesystem.localize_description(
            description,
            job_root_dir,
        )

        await filesystem.download(localized_description, description)

        # TODO for non-local file system should also remove remote files?
        if job.id is not None:
            await job_dao.update_job_state(job.id, state)

    return perform_download
