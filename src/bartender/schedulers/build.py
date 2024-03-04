from typing import Union

from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.arq import ArqScheduler, ArqSchedulerConfig
from bartender.schedulers.dirac_config import DiracSchedulerConfig
from bartender.schedulers.eager import EagerScheduler, EagerSchedulerConfig
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig
from bartender.schedulers.slurm import SlurmScheduler, SlurmSchedulerConfig
from bartender.shared.dirac_config import DIRAC_INSTALLED

SchedulerConfig = Union[
    MemorySchedulerConfig,
    SlurmSchedulerConfig,
    ArqSchedulerConfig,
    DiracSchedulerConfig,
    EagerSchedulerConfig,
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
    config2scheduler = {
        MemorySchedulerConfig: MemoryScheduler,
        SlurmSchedulerConfig: SlurmScheduler,
        ArqSchedulerConfig: ArqScheduler,
        EagerSchedulerConfig: EagerScheduler,
    }
    for cfgcls, schedulercls in config2scheduler.items():
        if isinstance(config, cfgcls):
            return schedulercls(config)
    if isinstance(config, DiracSchedulerConfig):
        if DIRAC_INSTALLED:
            from bartender.schedulers.dirac import (  # noqa: WPS433 is optional import
                DiracScheduler,
            )

            return DiracScheduler(config)
        raise ValueError("DIRAC package is not installed")
    raise ValueError(f"Unknown scheduler, recieved config is {config}")
