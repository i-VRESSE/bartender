from asyncio import create_subprocess_shell
from typing import Any, Literal, Optional

from arq import ArqRedis, Worker, create_pool
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus
from pydantic import BaseModel, RedisDsn, parse_obj_as

from bartender.db.models.job_model import State
from bartender.schedulers.abstract import AbstractScheduler, JobDescription


def _map_arq_status(arq_status: JobStatus, success: bool) -> State:
    status_map: dict[JobStatus, State] = {
        JobStatus.deferred: "queued",
        JobStatus.queued: "queued",
        JobStatus.in_progress: "running",
    }
    if arq_status == JobStatus.complete:
        if success:
            return "ok"
        return "error"
    try:
        return status_map[arq_status]
    except KeyError:
        # fallback to error when srq status is unmapped.
        return "error"


class ArqSchedulerConfig(BaseModel):
    """Configuration for ArqScheduler."""

    type: Literal["arq"] = "arq"
    redis_dsn: RedisDsn = parse_obj_as(RedisDsn, "redis://localhost:6379")
    queue: str = "arq:queue"

    @property
    def redis_settings(self) -> RedisSettings:
        """Settings for arq.

        :returns: The settings based on redis_dsn.
        """
        return RedisSettings.from_dsn(self.redis_dsn)


class ArqScheduler(AbstractScheduler):
    """Arq scheduler.

    See https://arq-docs.helpmanual.io/
    """

    def __init__(self, config: ArqSchedulerConfig) -> None:
        """Arq scheduler.

        :param config: The config.
        """
        self.config: ArqSchedulerConfig = config
        self.connection: Optional[ArqRedis] = None

    async def close(self) -> None:  # noqa: D102
        pool = await self._pool()
        await pool.close()

    async def submit(self, description: JobDescription) -> str:  # noqa: D102
        pool = await self._pool()
        job = await pool.enqueue_job("_exec", description)
        if job is None:
            # TODO better error?
            raise RuntimeError("Job already exists")
        return job.job_id

    async def state(self, job_id: str) -> State:  # noqa: D102
        pool = await self._pool()
        job = Job(job_id, pool)
        arq_status = await job.status()
        success = False
        if arq_status == JobStatus.complete:
            result = await job.result_info()
            if result is None:
                return "error"
            success = result.success
        return _map_arq_status(arq_status, success)

    async def cancel(self, job_id: str) -> None:  # noqa: D102
        pool = await self._pool()
        job = Job(job_id, pool)
        await job.abort()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ArqScheduler) and self.config == other.config

    def __repr__(self) -> str:
        return f"ArqScheduler(config={self.config})"

    async def _pool(self) -> ArqRedis:
        if self.connection is None:
            self.connection = await create_pool(
                self.config.redis_settings,
                default_queue_name=self.config.queue,
            )
        return self.connection


async def _exec(  # noqa: WPS210
    ctx: dict[Any, Any],
    description: JobDescription,
) -> None:
    stderr_fn = description.job_dir / "stderr.txt"
    stdout_fn = description.job_dir / "stdout.txt"

    with open(stderr_fn, "w") as stderr:
        with open(stdout_fn, "w") as stdout:
            proc = await create_subprocess_shell(
                description.command,
                stdout=stdout,
                stderr=stderr,
                cwd=description.job_dir,
            )
            returncode = await proc.wait()
            (description.job_dir / "returncode").write_text(str(returncode))
            # TODO raise exception when returncode != 0 ?


def arq_worker(config: ArqSchedulerConfig) -> None:
    """Worker that runs jobs submitted to arq queue.

    :param config: The config.
        Should be equal to the one used to submit job.
    """
    functions = [_exec]
    worker = Worker(
        redis_settings=config.redis_settings,
        queue_name=config.queue,
        functions=functions,  # type: ignore
    )
    worker.run()
