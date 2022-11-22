from typing import Any

from bartender._ssh_utils import SshConnectConfig
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.slurm import SlurmScheduler


def build(config: Any) -> AbstractScheduler:
    """Build scheduler instance from configuration.

    :param config: Configuration for a scheduler.
    :raises KeyError: When key is missing in configuration.
    :raises ValueError: When value is incorrect in configuration.
    :return: A scheduler instance.

    """
    scheduler_type = config.get("type")
    if scheduler_type is None:
        raise KeyError("Scheduler without type")
    if scheduler_type == "memory":
        return _build_memory_scheduler(config)
    if scheduler_type == "slurm":
        return _build_slurm_scheduler(config)
    raise ValueError(f'Scheduler with type {config["type"]} is unknown')


def _build_memory_scheduler(config: Any) -> MemoryScheduler:
    slots = config.get("slots")
    if slots is not None:
        return MemoryScheduler(slots)
    return MemoryScheduler()


def _build_slurm_scheduler(config: Any) -> SlurmScheduler:
    slurm_config = {
        sched_key: sched_value
        for sched_key, sched_value in config.items()
        if sched_key not in {"type", "ssh_config"}
    }
    ssh_config = config.get("ssh_config")
    if ssh_config is not None:
        ssh_config = SshConnectConfig(**ssh_config)
    return SlurmScheduler(ssh_config=ssh_config, **slurm_config)
