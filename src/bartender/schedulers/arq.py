from asyncio import TimeoutError, create_subprocess_shell, gather
from datetime import timedelta
from typing import Any, Literal, Optional, Union

from arq import ArqRedis, Worker, create_pool
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus
from pydantic import BaseModel, RedisDsn, parse_obj_as
from pydantic.types import PositiveInt

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
        # fallback to error when arq status is unmapped.
        return "error"


class ArqSchedulerConfig(BaseModel):
    """Configuration for ArqScheduler."""

    type: Literal["arq"] = "arq"
    redis_dsn: RedisDsn = parse_obj_as(RedisDsn, "redis://localhost:6379")
    queue: str = "arq:queue"
    max_jobs: PositiveInt = 10  # noqa: WPS462
    """Maximum number of jobs to run at a time inside a single worker."""  # noqa: E501, WPS322, WPS428
    job_timeout: Union[PositiveInt, timedelta] = 3600  # noqa: WPS462
    """Maximum job run time.

    Default is one hour.

    In seconds or string in `ISO 8601 duration format <https://en.wikipedia.org/wiki/ISO_8601#Durations>`_.

    For example, "PT12H" represents a max runtime of "twelve hours".
    """  # noqa: E501, WPS428

    @property
    def redis_settings(self) -> RedisSettings:
        """Settings for arq.

        Returns:
            The settings based on redis_dsn.
        """
        return RedisSettings.from_dsn(self.redis_dsn)


class ArqScheduler(AbstractScheduler):
    """Arq scheduler.

    See https://arq-docs.helpmanual.io/.
    """

    def __init__(self, config: ArqSchedulerConfig) -> None:
        """Arq scheduler.

        Args:
            config: The config.
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
        if arq_status == JobStatus.not_found:
            raise KeyError(job_id)
        if arq_status == JobStatus.complete:
            result = await job.result_info()
            if result is None:
                raise RuntimeError(
                    f"Failed to fetch result from completed arq job {job_id}",
                )
            success = result.success
        return _map_arq_status(arq_status, success)

    async def cancel(self, job_id: str) -> None:  # noqa: D102
        pool = await self._pool()
        job = Job(job_id, pool)
        try:
            await job.abort(timeout=0.1)
        except TimeoutError:
            # job.result() times out on cancelled queued job
            return

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ArqScheduler) and self.config == other.config

    def __repr__(self) -> str:
        config = repr(self.config)
        return f"ArqScheduler(config={config})"

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


def arq_worker(config: ArqSchedulerConfig, burst: bool = False) -> Worker:
    """Worker that runs jobs submitted to arq queue.

    Args:
        config: The config. Should be equal to the one used to submit job.
        burst: Whether to stop the worker once all jobs have been run.

    Returns:
        A worker.
    """
    functions = [_exec]
    return Worker(
        redis_settings=config.redis_settings,
        queue_name=config.queue,
        max_jobs=config.max_jobs,
        job_timeout=config.job_timeout,
        functions=functions,  # type: ignore
        burst=burst,
        allow_abort_jobs=True,
    )


async def run_workers(configs: list[ArqSchedulerConfig]) -> None:
    """Run worker for each arq scheduler config.

    Args:
        configs: The configs.
    """
    workers = [arq_worker(config) for config in configs]
    await gather(*[worker.async_run() for worker in workers])
