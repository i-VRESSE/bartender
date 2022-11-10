from asyncio import Queue, create_subprocess_shell, create_task, gather
from string import Template
from uuid import uuid4

from pydantic import BaseModel
from pydantic.types import PositiveInt

from bartender.db.models.job_model import CompletedStates, State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription
from bartender.settings import settings


class _Job(BaseModel):
    description: JobDescription
    id: str


async def _exec(job: _Job, states: dict[str, State]) -> None:  # noqa: WPS210
    description = job.description
    job_id = job.id
    job_dir = description.job_dir
    app = settings.applications[description.app]
    cmd = Template(app.command).substitute(config=app.config)
    stderr_fn = job_dir / "stderr.txt"
    stdout_fn = job_dir / "stdout.txt"

    with open(stderr_fn, "w") as stderr:
        with open(stdout_fn, "w") as stdout:
            states[job_id] = "running"
            proc = await create_subprocess_shell(
                cmd,
                stdout=stdout,
                stderr=stderr,
                cwd=job_dir,
            )
            returncode = await proc.wait()
            if returncode == 0:
                states[job_id] = "ok"
            else:
                states[job_id] = "error"
            (job_dir / "returncode").write_text(str(returncode))


async def _worker(queue: Queue[_Job], states: dict[str, State]) -> None:
    while True:  # noqa: WPS457
        job = await queue.get()
        await _exec(job, states)
        queue.task_done()


class MemoryScheduler(AbstractScheduler):
    """In memory scheduler.

    When service is terminated any queud or running jobs wiil disappear.
    """

    def __init__(self, slots: PositiveInt = 1):
        """In memory scheduler.

        :param slots: Maximum number of concurrently runnning jobs.
        """
        self.queue: Queue[_Job] = Queue()
        self.states: dict[str, State] = {}
        self.tasks = []
        for _ in range(slots):
            task = create_task(_worker(self.queue, self.states))
            self.tasks.append(task)

    async def close(self) -> None:  # noqa: D102
        for task in self.tasks:
            task.cancel()
        await gather(*self.tasks, return_exceptions=True)

    async def submit(self, description: JobDescription) -> str:  # noqa: D102
        job_id = str(uuid4())
        self.states[job_id] = "queued"
        job = _Job(description=description, id=job_id)
        await self.queue.put(job)
        return job_id

    async def state(self, job_id: str) -> State:  # noqa: D102
        state = self.states[job_id]
        if state in CompletedStates:
            # Forget completed jobs
            del self.states[job_id]  # noqa: WPS420
        return state

    async def cancel(self, job_id: str) -> None:  # noqa: D102
        state = self.states[job_id]
        if state in CompletedStates:
            # Forget completed jobs
            del self.states[job_id]  # noqa: WPS420
        if state == "running":
            # TODO find task busy with job and cancel it
            raise NotImplementedError()
        if state == "queued":
            # TODO remove job from queue
            raise NotImplementedError()
