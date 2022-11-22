from dataclasses import dataclass
from typing import Any

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.build import build as build_filesystem
from bartender.filesystems.local import LocalFileSystem
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.build import build as build_scheduler
from bartender.schedulers.memory import MemoryScheduler


@dataclass
class Destination:
    """A destination is a combination of a scheduler and optional filesystem."""

    scheduler: AbstractScheduler
    filesystem: AbstractFileSystem = LocalFileSystem()


def build(config: Any) -> dict[str, Destination]:
    """Build job destinations dictionary from a configuration dictionary.

    :param config: The configuration dictionary.
    :return: Job destinations dictionary
    """
    if not config:
        return {
            "": Destination(scheduler=MemoryScheduler()),
        }

    destinations = {}
    for name, dest_config in config.items():
        destinations[name] = _build_destination(dest_config)
    return destinations


def _build_destination(dest_config: Any) -> Destination:
    if not dest_config:
        raise KeyError("A destination needs scheduler and optional file system")
    scheduler = build_scheduler(dest_config["scheduler"])
    filesystem: AbstractFileSystem = LocalFileSystem()
    filesystem_config = dest_config.get("filesystem")
    if filesystem_config is not None:
        filesystem = build_filesystem(dest_config["filesystem"])
    return Destination(scheduler=scheduler, filesystem=filesystem)
