from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from bartender.destinations import (
    Destination,
    DestinationConfig,
    build,
    default_destinations,
)
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.schedulers.abstract import AbstractScheduler
from bartender.schedulers.memory import MemoryScheduler, MemorySchedulerConfig


class TestDestinationConfig:
    def test_unknown_scheduler_type(self) -> None:
        with pytest.raises(ValidationError):
            raw_config = {
                "scheduler": {"type": "XYZscheduler"},
                "filesystem": {"type": "local"},
            }
            DestinationConfig(**raw_config)

    def test_unknown_filesystem_type(self) -> None:
        with pytest.raises(ValidationError):
            raw_config = {
                "scheduler": {"type": "memory"},
                "filesystem": {"type": "XYZfilesystem"},
            }
            DestinationConfig(**raw_config)


def test_default_destinations() -> None:
    destinations = default_destinations()

    expected = {
        "": DestinationConfig(
            scheduler=MemorySchedulerConfig(),
            filesystem=LocalFileSystemConfig(),
        ),
    }
    assert destinations == expected


class TestDestination:
    @pytest.mark.anyio
    async def test_close(self) -> None:
        scheduler = AsyncMock(AbstractScheduler)
        filesystem = MagicMock(AbstractFileSystem)

        destination = Destination(scheduler=scheduler, filesystem=filesystem)

        await destination.close()

        filesystem.close.assert_called_once_with()
        scheduler.close.assert_called_once_with()


class TestBuild:
    def test_empty(self) -> None:
        config: dict[str, DestinationConfig] = {}

        destinations = build(config)

        expected: dict[str, Destination] = {}
        assert destinations == expected

    @pytest.mark.anyio
    async def test_one_destination(self) -> None:
        try:
            config = {
                "dest1": DestinationConfig(
                    scheduler=MemorySchedulerConfig(),
                    filesystem=LocalFileSystemConfig(),
                ),
            }

            destinations = build(config)

            expected = {
                "dest1": Destination(
                    scheduler=MemoryScheduler(MemorySchedulerConfig()),
                    filesystem=LocalFileSystem(),
                ),
            }
            assert destinations == expected
        finally:
            await destinations["dest1"].close()
            await expected["dest1"].close()

    @pytest.mark.anyio
    async def test_two_destinations(self) -> None:
        try:
            config = {
                "dest1": DestinationConfig(
                    scheduler=MemorySchedulerConfig(),
                    filesystem=LocalFileSystemConfig(),
                ),
                "dest2": DestinationConfig(
                    scheduler=MemorySchedulerConfig(slots=2),
                    filesystem=LocalFileSystemConfig(),
                ),
            }

            destinations = build(config)

            expected = {
                "dest1": Destination(
                    scheduler=MemoryScheduler(MemorySchedulerConfig()),
                    filesystem=LocalFileSystem(),
                ),
                "dest2": Destination(
                    scheduler=MemoryScheduler(MemorySchedulerConfig(slots=2)),
                    filesystem=LocalFileSystem(),
                ),
            }
            assert destinations == expected
        finally:
            await destinations["dest1"].close()
            await expected["dest1"].close()
