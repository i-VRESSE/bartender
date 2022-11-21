import pytest

from bartender.destinations import Destination, build
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


@pytest.mark.anyio
async def test_empty():
    config = {}
    result = build(config)

    expected = {
        "": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem())
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_empty():
    config = {"dest1": {}}
    with pytest.raises(KeyError):
        build(config)


@pytest.mark.anyio
async def test_single_memory():
    config = {"dest1": {"scheduler": {"type": "memory"}}}
    result = build(config)

    expected = {
        "dest1": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem())
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_memory_local():
    config = {
        "dest1": {"scheduler": {"type": "memory"}, "filesystem": {"type": "local"}}
    }
    result = build(config)

    expected = {
        "dest1": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem())
    }
    assert result == expected


@pytest.mark.anyio
async def test_double():

    config = {
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
            scheduler=MemoryScheduler(slots=42), filesystem=LocalFileSystem()
        ),
        "dest2": Destination(
            scheduler=SlurmScheduler(
                runner=SshCommandRunner(config={"hostname": "localhost"}),
                partition="mypartition",
            ),
            filesystem=SftpFileSystem(
                config={
                    "hostname": "localhost",
                },
                entry="/scratch/jobs",
            ),
        ),
    }
    assert result == expected
