from asyncio import Queue, create_task, gather
from typing import Any, Callable, Coroutine

from fastapi import FastAPI, Request

FileStagingQueue = Queue[Callable[[], Coroutine[Any, Any, None]]]


async def _file_staging_worker(queue: FileStagingQueue) -> None:
    while True:  # noqa: WPS457 can be escaped by task.cancel() throwing CancelledError
        copy_command = await queue.get()
        await copy_command()
        queue.task_done()


def build_file_staging_queue(app: FastAPI) -> None:
    """Create file staging queue and inject in to app state.

    :param app: fastAPI application.
    """
    queue: FileStagingQueue = Queue()
    app.state.file_staging_queue_task = create_task(_file_staging_worker(queue))
    app.state.file_staging_queue = queue


async def teardown_file_staging_queue(app: FastAPI) -> None:
    """Stop file staging queue and its task consumer.

    :param app: fastAPI application.
    """
    # TODO Should we complete queued+running file staging tasks
    # or leave incomplete (=current)?
    # await app.state.file_staging_queue.join()
    app.state.file_staging_queue_task.cancel()
    await gather(app.state.file_staging_queue_task, return_exceptions=True)


def get_file_staging_queue(request: Request) -> FileStagingQueue:
    """Retrieve file staging queue.

    :param request: The request injected by FastAPI.
    :return: queue for downloading/uploading files from/to remote filesystems.
    """
    return request.state.file_staging_queue
