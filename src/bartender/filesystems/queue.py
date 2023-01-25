from asyncio import Queue, Task, create_task, gather
from typing import Any, Callable, Coroutine

from fastapi import FastAPI, Request

FileStagingQueue = Queue[Callable[[], Coroutine[Any, Any, None]]]


async def _file_staging_worker(queue: FileStagingQueue) -> None:
    while True:  # noqa: WPS457 can be escaped by task.cancel() throwing CancelledError
        copy_command = await queue.get()
        await copy_command()
        queue.task_done()


def setup_file_staging_queue(app: FastAPI) -> None:
    """Create file staging queue and inject in to app state.

    :param app: FastAPI application.
    """
    queue, task = build_file_staging_queue()
    app.state.file_staging_queue = queue
    app.state.file_staging_queue_task = task


def build_file_staging_queue() -> tuple[FileStagingQueue, Task[None]]:
    """Create file staging queue and single worker task.

    :return: The queue and the task.
    """
    queue: FileStagingQueue = Queue()
    task = create_task(_file_staging_worker(queue))
    return queue, task


async def stop_file_staging_queue(task: Task[None]) -> None:
    """Stop file staging queue and its task consumer.

    :param task: Task to cancel and wait for.
    """
    # TODO Should we complete queued+running file staging tasks
    # or leave incomplete (=current)?
    # await queue.join()
    task.cancel()
    await gather(task, return_exceptions=True)


async def teardown_file_staging_queue(app: FastAPI) -> None:
    """Stop file staging queue and its task consumer.

    :param app: fastAPI application.
    """
    await stop_file_staging_queue(app.state.file_staging_queue_task)


def get_file_staging_queue(request: Request) -> FileStagingQueue:
    """Retrieve file staging queue.

    :param request: The request injected by FastAPI.
    :return: queue for downloading/uploading files from/to remote filesystems.
    """
    return request.app.state.file_staging_queue
