from dataclasses import dataclass

from pydantic import BaseModel, Field

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.build import FileSystemConfig
from bartender.filesystems.build import build as build_filesystem
from bartender.filesystems.local import LocalFileSystemConfig
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.build import SchedulerConfig
from bartender.schedulers.build import build as build_scheduler
from bartender.schedulers.memory import MemorySchedulerConfig


class DestinationConfig(BaseModel):
    """Configuration for job destination."""

    scheduler: SchedulerConfig = Field(discriminator="type")
    filesystem: FileSystemConfig = Field(discriminator="type")

    # TODO validate that some combinations of scheduler and file system
    # are not possible like
    # * MemoryScheduler + SftpFileSystem
    # In future possible combos
    # * AWSBatchScheduler + S3FileSystem
    # * DiracScheduler + SrmFileSystem


def default_destinations() -> dict[str, DestinationConfig]:
    """Default destinations when empty dict was given as Config.destinations.

    :returns: Dict with local in-memory scheduler and file system.
    """
    return {
        "": DestinationConfig(
            scheduler=MemorySchedulerConfig(),
            filesystem=LocalFileSystemConfig(),
        ),
    }


@dataclass
class Destination:
    """A destination is a combination of a scheduler and optional filesystem."""

    scheduler: AbstractScheduler
    filesystem: AbstractFileSystem

    async def close(self) -> None:
        """Cleanup destination.

        A job destination can have connections to remote systems.
        Call this method to clean those up.
        """
        await self.scheduler.close()
        self.filesystem.close()


def build(config: dict[str, DestinationConfig]) -> dict[str, Destination]:
    """Build job destinations dictionary from a configuration dictionary.

    :param config: The configuration dictionary.
    :return: Job destinations dictionary
    """
    destinations = {}
    for name, dest_config in config.items():
        destinations[name] = build_destination(dest_config)
    return destinations


def build_destination(config: DestinationConfig) -> Destination:
    """Build job destination from configuration.

    :param config: Configuration for a destination.
    :returns: A job destination.
    """
    scheduler = build_scheduler(config.scheduler)
    filesystem = build_filesystem(config.filesystem)
    return Destination(scheduler=scheduler, filesystem=filesystem)
