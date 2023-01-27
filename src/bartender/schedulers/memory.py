from asyncio import (
    CancelledError,
    Queue,
    Task,
    create_subprocess_shell,
    create_task,
    gather,
)
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel
from pydantic.types import PositiveInt

from bartender.db.models.job_model import CompletedStates, State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription


class _Job(BaseModel):
    description: JobDescription
    id: str
    state: State
    worker_index: Optional[int] = None


KILLED_RETURN_CODE = "130"


async def _exec(job: _Job) -> None:  # noqa: WPS210
    job_dir = job.description.job_dir
    stderr_fn = job_dir / "stderr.txt"
    stdout_fn = job_dir / "stdout.txt"

    with open(stderr_fn, "w") as stderr:
        with open(stdout_fn, "w") as stdout:
            job.state = "running"
            try:
                proc = await create_subprocess_shell(
                    job.description.command,
                    stdout=stdout,
                    stderr=stderr,
                    cwd=job_dir,
                )
                returncode = await proc.wait()
                if returncode == 0:
                    job.state = "ok"
                else:
                    job.state = "error"
                (job_dir / "returncode").write_text(str(returncode))
            except CancelledError as exc:
                proc.kill()
                # TODO job was killed by external action,
                # use different state like killed?
                job.state = "error"
                (job_dir / "returncode").write_text(KILLED_RETURN_CODE)
                raise exc


async def _worker(queue: Queue[_Job], jobs: dict[str, _Job], worker_index: int) -> None:
    while True:  # noqa: WPS457
        job = await queue.get()
        # cannot delete job from queue to cancel it
        # workaround is to skip job when it is not in jobs dict
        # as MemoryScheduler.cancel() will remove job from dict
        if job.id in jobs:
            job.worker_index = worker_index
            await _exec(job)
        queue.task_done()


class MemorySchedulerConfig(BaseModel):
    """Configuration for in memory scheduler.

    :param slots: Maximum number of concurrently runnning jobs. Minimum is 1.
    """

    type: Literal["memory"] = "memory"
    slots: PositiveInt = 1


class MemoryScheduler(AbstractScheduler):
    """In memory scheduler.

    When service is closed any queud or running jobs will disappear.

    """

    # TODO when running uvicorn with workers>1 then
    # there are multiple instances of this class
    # this can cause
    # * having multiple jobs running even when slot=1
    # * asking job state from instance that is not running that job
    # Should add warning to only use with workers=1 or reload=True
    # And add alternative redis scheduler using Celery, RQ or arq
    # Or have single instance created in __main__.py

    def __init__(self, config: MemorySchedulerConfig):
        """In memory scheduler.

        :param config: The config.
        """
        self.queue: Queue[_Job] = Queue()
        self.jobs: dict[str, _Job] = {}
        self.workers: list[Task[None]] = []
        for _ in range(config.slots):
            self._add_worker()

    async def close(self) -> None:  # noqa: D102
        for task in self.workers:
            task.cancel()
        await gather(*self.workers, return_exceptions=True)

    async def submit(self, description: JobDescription) -> str:  # noqa: D102
        job_id = str(uuid4())
        job = _Job(description=description, id=job_id, state="queued")
        self.jobs[job_id] = job
        await self.queue.put(job)
        return job_id

    async def state(self, job_id: str) -> State:  # noqa: D102
        state = self.jobs[job_id].state
        self._forget_completed_job(job_id, state)
        return state

    async def cancel(self, job_id: str) -> None:  # noqa: D102
        job = self.jobs[job_id]
        self._forget_completed_job(job_id, job.state)
        if job.state == "running" and job.worker_index is not None:
            self.workers[job.worker_index].cancel()
            self._add_worker()
        if job.state == "queued":
            self.jobs.pop(job_id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MemoryScheduler) and len(self.workers) == len(
            other.workers,
        )

    def __repr__(self) -> str:
        slots = len(self.workers)
        return f"MemoryScheduler(slots={slots})"

    def _add_worker(self) -> None:
        worker_index = len(self.workers)
        worker = create_task(_worker(self.queue, self.jobs, worker_index))
        self.workers.append(worker)
        worker.add_done_callback(self.workers.remove)

    def _forget_completed_job(self, job_id: str, state: State) -> None:
        if state in CompletedStates:
            self.jobs.pop(job_id)
