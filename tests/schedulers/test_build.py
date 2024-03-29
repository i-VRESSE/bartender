import pytest
from pydantic import RedisDsn

from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.arq import ArqScheduler, ArqSchedulerConfig
from bartender.schedulers.build import SchedulerConfig, build
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig


async def run_it(config: SchedulerConfig, expected: AbstractScheduler) -> None:
    result = build(config)
    try:  # noqa: WPS501
        assert result == expected
    finally:
        await result.close()
        await expected.close()


@pytest.mark.anyio
async def test_single_memory_scheduler() -> None:
    config = MemorySchedulerConfig()
    expected = MemoryScheduler(config)
    await run_it(config, expected)


@pytest.mark.anyio
async def test_single_local_slurm_scheduler() -> None:
    config = SlurmSchedulerConfig()
    expected = SlurmScheduler(config)
    await run_it(config, expected)


@pytest.mark.anyio
async def test_single_local_arq_scheduler(redis_dsn: RedisDsn) -> None:
    config = ArqSchedulerConfig(redis_dsn=redis_dsn)
    expected = ArqScheduler(config)
    await run_it(config, expected)
