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

    Args:
        job: Job instance.
        job_dao: JobDAO object.
        destination: Job destination used to submit job.
        job_root_dir: Directory where all jobs can be found.
        file_staging_queue: When scheduler reports job is complete.
            The output files need to be copied back.
            Use queue to perform download outside request/response handling.
    """
    if job.state not in CompletedStates and job.internal_id is not None:
        state = await destination.scheduler.state(job.internal_id)
        updater = UpdateStateHelper(
            job_dao,
            job_root_dir,
            file_staging_queue,
        )
        await updater(
            job,
            state,
            destination.filesystem,
        )


class UpdateStateHelper:
    """Takes the new state of a job and stores it in the database.

    When job is completed then the output files should be downloaded.
    To not block the `GET /api/job/:jobid` the downloading is queued up.
    """

    def __init__(
        self,
        job_dao: JobDAO,
        job_root_dir: Path,
        file_staging_queue: FileStagingQueue,
    ):
        """Contruct with non job specific arguments.

        Args:
            job_dao: Object to update jobs in database.
            job_root_dir: In which directory the job directory was made.
            file_staging_queue: Queue used to defer downloading.
        """
        self.job_dao = job_dao
        self.job_root_dir = job_root_dir
        self.file_staging_queue = file_staging_queue

    async def __call__(
        self,
        job: Job,
        state: State,
        filesystem: AbstractFileSystem,
    ) -> None:
        """Perform update with job specific arguments.

        Args:
            job: Job for which new state should be set.
            state: The new state, most likely retrieved from a
                scheduler.
            filesystem: Filesystem on which scheduler executed the job.
                Where the output files of the job reside.
        """
        if job.state != state and job.id is not None and job.state != "staging_out":
            if state in CompletedStates:
                # when scheduler says job is completed then download output files
                await self.job_dao.update_job_state(job.id, "staging_out")
                perform_download = download2queue(
                    job,
                    self.job_dao,
                    state,
                    filesystem,
                    self.job_root_dir,
                )
                await self.file_staging_queue.put(perform_download)
                # as once download is complete the state in db will be updated
            else:
                await self.job_dao.update_job_state(job.id, state)
                job.state = state


async def sync_states(
    jobs: list[Job],
    destinations: dict[str, Destination],
    job_dao: JobDAO,
    job_root_dir: Path,
    file_staging_queue: FileStagingQueue,
) -> None:
    """Sync state of jobs from scheduler to database.

    Args:
        jobs: Job instances.
        destinations: Job destinations.
        job_dao: JobDAO object.
        job_root_dir: Directory where all jobs can be found.
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
    updater = UpdateStateHelper(
        job_dao,
        job_root_dir,
        file_staging_queue,
    )
    for job in jobs2sync:
        if job.id is None or job.destination is None:
            continue  # mypy type narrowing, should never get here
        await updater(
            job,
            states[job.id],
            destinations[job.destination].filesystem,
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


def download2queue(
    job: Job,
    job_dao: JobDAO,
    state: State,
    filesystem: AbstractFileSystem,
    job_root_dir: Path,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Generate dowload function that can be queued for later execution.

    The function will
    1. Download files from job on `filesystem` to `job_root_dir/job.id`.
    2. Update state of job in db to `state`.

    Args:
        job: Completed job to download for.
        job_dao: Object to interact with database.
        state: The new state to set.
        filesystem: File system where job wrote its output files.
        job_root_dir: Directory on server where this Python process is
            running. A subdirectory of this is the job directory and the
            destination to copy files to.

    Returns:
        Function that can be passed to `FileStagingQueue.put(item)`.
    """
    # TODO instead of passing function to queue,
    # pass just the (job.id, state and destination_name)
    # this would make it possible to switch from async queue to arq queue
    # as all arguments are then serializable

    async def perform_download() -> None:  # noqa: WPS430 queue.put recieves function
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
