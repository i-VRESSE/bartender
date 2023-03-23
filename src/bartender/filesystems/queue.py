from asyncio import Queue, Task, create_task, gather
from pathlib import Path

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import async_scoped_session

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import State
from bartender.destinations import Destination
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription

FileStagingQueue = Queue[tuple[int, str, State]]  # noqa: WPS462
"""Custom type for file staging queue.

The `item` argument in `queue.put(item)` method should be
an async function without any arguments.
"""  # noqa: WPS428


async def perform_download(
    job_root_dir: Path,
    job_id: int,
    filesystem: AbstractFileSystem,
    job_dao: JobDAO,
    state: State,
) -> None:
    """Download files of job from job's destination filesystem to local filesystem.

    When completed the state of the job is set to the given state.

    Args:
        job_root_dir: Local job root directory.
        job_id: Job identifier to download files for.
        filesystem: Filesystem to download files from.
        job_dao: Object to update jobs in database.
        state: The new state, most likely retrieved from a
            scheduler.
    """
    job_dir: Path = job_root_dir / str(job_id)
    # Command does not matter for downloading so use dummy command echo.
    description = JobDescription(job_dir=job_dir, command="echo")
    localized_description = filesystem.localize_description(
        description,
        job_root_dir,
    )

    await filesystem.download(localized_description, description)

    # TODO for non-local file system should also remove remote files?

    if job_id is not None:
        await job_dao.update_job_state(job_id, state)


async def _file_staging_worker(
    queue: FileStagingQueue,
    job_root_dir: Path,
    destinations: dict[str, Destination],
    factory: async_scoped_session,
) -> None:
    while True:  # noqa: WPS457 can be escaped by task.cancel() throwing CancelledError
        (job_id, destination_name, state) = await queue.get()
        async with factory() as session:
            filesystem = destinations[destination_name].filesystem
            await perform_download(
                job_root_dir,
                job_id,
                filesystem,
                JobDAO(session),
                state,
            )
        queue.task_done()


def setup_file_staging_queue(app: FastAPI) -> None:
    """Create file staging queue and inject in to app state.

    Args:
        app: FastAPI application.
    """
    factory = app.state.db_session_factory
    job_root_dir = app.state.config.job_root_dir
    destinations = app.state.context.destinations
    queue, task = build_file_staging_queue(job_root_dir, destinations, factory)
    app.state.file_staging_queue = queue
    app.state.file_staging_queue_task = task


def build_file_staging_queue(
    job_root_dir: Path,
    destinations: dict[str, Destination],
    factory: async_scoped_session,
) -> tuple[FileStagingQueue, Task[None]]:
    """Create file staging queue and single worker task.

    Args:
        job_root_dir: Job root directory.
        destinations: Job destination dictionary.
        factory: Database session factory.

    Returns:
        Tuple with the queue and the task.
    """
    queue: FileStagingQueue = Queue()
    task = create_task(_file_staging_worker(queue, job_root_dir, destinations, factory))
    return queue, task


async def stop_file_staging_queue(task: Task[None]) -> None:
    """Stop file staging queue and its task consumer.

    Args:
        task: Task to cancel and wait for.
    """
    # TODO Should we complete queued+running file staging tasks
    # or leave incomplete (=current)?
    # await queue.join()
    task.cancel()
    await gather(task, return_exceptions=True)


async def teardown_file_staging_queue(app: FastAPI) -> None:
    """Stop file staging queue and its task consumer.

    Args:
        app: fastAPI application.
    """
    await stop_file_staging_queue(app.state.file_staging_queue_task)


def get_file_staging_queue(request: Request) -> FileStagingQueue:
    """Retrieve file staging queue.

    Args:
        request: The request injected by FastAPI.

    Returns:
        queue for downloading/uploading files from/to remote
        filesystems.

    Can be used in dependency injection in a FastAPI route.
    Requires :func:`setup_file_staging_queue` and :func:`teardown_file_staging_queue`
    to be added to FastAPI startup and shutdown events.

    For example

    .. code-block:: python

        @router.get("/staging-queue-size")
        async def file_staging_queue_size(
            file_staging_queue: FileStagingQueue = Depends(get_file_staging_queue),
        ):
            return file_staging_queue.qsize()

    """
    return request.app.state.file_staging_queue
