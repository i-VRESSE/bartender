from typing import Union

from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig

SchedulerConfig = Union[MemorySchedulerConfig, SlurmSchedulerConfig]


def build(config: SchedulerConfig) -> AbstractScheduler:
    """Build scheduler instance from configuration.

    :param config: Configuration for a scheduler.
    :raises ValueError: When config can not be mapped to a scheduler instance.
    :return: A scheduler instance.

    """
    if isinstance(config, MemorySchedulerConfig):
        return MemoryScheduler(config)
    if isinstance(config, SlurmSchedulerConfig):
        return SlurmScheduler(config)
    raise ValueError(f"Unknown scheduler, recieved config is {config}")
