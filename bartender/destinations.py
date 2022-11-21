from dataclasses import dataclass
from typing import Any, Optional


from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.build import build as build_filesystem
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.build import build as build_scheduler


@dataclass
class Destination:
    scheduler: AbstractScheduler
    filesystem: Optional[AbstractFileSystem] = None


def build(config: Any) -> dict[str, Destination]:
    if not config:
        return {
            "": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem())
        }

    destinations = {}
    for name, dest_config in config.items():
        if not dest_config:
            raise KeyError("Destinations needs scheduler and optional file system")
        scheduler = build_scheduler(dest_config["scheduler"])
        filesystem = LocalFileSystem()
        if "filesystem" in dest_config:
            filesystem = build_filesystem(dest_config["filesystem"])           
        destinations[name] = Destination(scheduler=scheduler, filesystem=filesystem)
    return destinations
