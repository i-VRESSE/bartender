import pytest

from bartender.schedulers.build import build
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig


@pytest.mark.anyio
async def test_memory_scheduler() -> None:
    try:
        config = MemorySchedulerConfig()

        result = build(config)

        expected = MemoryScheduler(config)
        assert result == expected
    finally:
        await result.close()
        await expected.close()


@pytest.mark.anyio
async def test_slurm_scheduler() -> None:
    try:
        config = SlurmSchedulerConfig()

        result = build(config)

        expected = SlurmScheduler(config)
        assert result == expected
    finally:
        await result.close()
        await expected.close()
