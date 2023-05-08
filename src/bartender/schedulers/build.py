from typing import Union

from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.arq import ArqScheduler, ArqSchedulerConfig
from bartender.schedulers.dirac_config import DiracSchedulerConfig
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig
from bartender.shared.dirac import DIRAC_INSTALLED

SchedulerConfig = Union[
    MemorySchedulerConfig,
    SlurmSchedulerConfig,
    ArqSchedulerConfig,
    DiracSchedulerConfig,
]


def build(config: SchedulerConfig) -> AbstractScheduler:
    """Build scheduler instance from configuration.

    Args:
        config: Configuration for a scheduler.

    Raises:
        ValueError: When config can not be mapped to a scheduler instance.

    Returns:
        A scheduler instance.

    """
    if isinstance(config, MemorySchedulerConfig):
        return MemoryScheduler(config)
    if isinstance(config, SlurmSchedulerConfig):
        return SlurmScheduler(config)
    if isinstance(config, ArqSchedulerConfig):
        return ArqScheduler(config)
    if isinstance(config, DiracSchedulerConfig):
        if DIRAC_INSTALLED:
            from bartender.schedulers.dirac import (  # noqa: WPS433 is optional import
                DiracScheduler,
            )

            return DiracScheduler(config)
        raise ValueError("DIRAC package is not installed")
    raise ValueError(f"Unknown scheduler, recieved config is {config}")
