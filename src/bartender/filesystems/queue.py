from asyncio import Queue, Task, create_task, gather
from typing import Any, Callable, Coroutine

from fastapi import FastAPI, Request

FileStagingQueue = Queue[Callable[[], Coroutine[Any, Any, None]]]  # noqa: WPS462
"""Custom type for file staging queue.

The `item` argument in `queue.put(item)` method should be
an async function without any arguments.
"""  # noqa: WPS428


async def _file_staging_worker(queue: FileStagingQueue) -> None:
    while True:  # noqa: WPS457 can be escaped by task.cancel() throwing CancelledError
        copy_command = await queue.get()
        await copy_command()
        queue.task_done()


def setup_file_staging_queue(app: FastAPI) -> None:
    """Create file staging queue and inject in to app state.

    Args:
        app: FastAPI application.
    """
    queue, task = build_file_staging_queue()
    app.state.file_staging_queue = queue
    app.state.file_staging_queue_task = task


def build_file_staging_queue() -> tuple[FileStagingQueue, Task[None]]:
    """Create file staging queue and single worker task.

    Returns:
        The queue and the task.
    """
    queue: FileStagingQueue = Queue()
    task = create_task(_file_staging_worker(queue))
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
