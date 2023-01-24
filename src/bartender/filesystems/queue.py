from asyncio import Queue, create_task
from typing import Awaitable, Callable

from fastapi import FastAPI, Request

FileStagingQueue = Queue[Awaitable[Callable]]


async def file_staging_worker(queue: FileStagingQueue):
    while True:
        copy_command = await queue.get()
        await copy_command()
        queue.task_done()


async def build_file_staging_queue() -> FileStagingQueue:
    queue = Queue()
    create_task(file_staging_worker(queue))
    return queue


def get_file_staging_queue():
    queue = build_file_staging_queue()
    try:
        yield queue
    finally:
        queue.close()
