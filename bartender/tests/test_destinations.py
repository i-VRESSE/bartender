from pathlib import Path
from typing import Any

import pytest

from bartender._ssh_utils import SshConnectConfig
from bartender.destinations import Destination, build
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


@pytest.mark.anyio
async def test_empty() -> None:
    config: Any = {}
    result = build(config)

    expected = {
        "": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem()),
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_empty() -> None:
    config: Any = {"dest1": {}}
    with pytest.raises(KeyError):
        build(config)


@pytest.mark.anyio
async def test_single_memory() -> None:
    config: Any = {"dest1": {"scheduler": {"type": "memory"}}}
    result = build(config)

    expected = {
        "dest1": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem()),
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_memory_local() -> None:
    config: Any = {
        "dest1": {"scheduler": {"type": "memory"}, "filesystem": {"type": "local"}},
    }
    result = build(config)

    expected = {
        "dest1": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem()),
    }
    assert result == expected


@pytest.mark.anyio
async def test_double() -> None:
    config: Any = {
        "dest1": {"scheduler": {"type": "memory", "slots": 42}},
        "dest2": {
            "scheduler": {
                "type": "slurm",
                "partition": "mypartition",
                "runner": {
                    "type": "ssh",
                    "hostname": "localhost",
                },
            },
            "filesystem": {
                "type": "sftp",
                "config": {
                    "hostname": "localhost",
                },
                "entry": "/scratch/jobs",
            },
        },
    }
    result = build(config)

    expected = {
        "dest1": Destination(
            scheduler=MemoryScheduler(slots=42),
            filesystem=LocalFileSystem(),
        ),
        "dest2": Destination(
            scheduler=SlurmScheduler(
                runner=SshCommandRunner(config=SshConnectConfig(hostname="localhost")),
                partition="mypartition",
            ),
            filesystem=SftpFileSystem(
                config=SshConnectConfig(hostname="localhost"),
                entry=Path("/scratch/jobs"),
            ),
        ),
    }
    assert result == expected
