from typing import Any

import pytest

from bartender._ssh_utils import SshConnectConfig
from bartender.schedulers.build import build
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.slurm import SlurmScheduler


def test_single_typeless_scheduler() -> None:
    config: Any = {}
    with pytest.raises(KeyError):
        build(config)


def test_single_unknown_scheduler() -> None:
    config = {"type": "unknown"}
    with pytest.raises(ValueError):
        build(config)


@pytest.mark.anyio
async def test_single_memory_scheduler() -> None:
    config = {"type": "memory"}
    result = build(config)

    expected = MemoryScheduler()
    assert result == expected


@pytest.mark.anyio
async def test_single_custom_memory_scheduler() -> None:
    config = {"type": "memory", "slots": 4}
    result = build(config)

    expected = MemoryScheduler(slots=4)
    assert result == expected


@pytest.mark.anyio
async def test_single_localsimplist_slurm_scheduler() -> None:
    config = {"type": "slurm"}
    result = build(config)

    expected = SlurmScheduler()
    assert result == expected


@pytest.mark.anyio
async def test_single_localcustom_slurm_scheduler() -> None:
    config = {
        "type": "slurm",
        "partition": "mypartition",
        "time": "60",
        "extra_options": ["--nodes 1"],
    }
    result = build(config)

    expected = SlurmScheduler(
        partition="mypartition",
        time="60",
        extra_options=["--nodes 1"],
    )
    assert result == expected


@pytest.mark.anyio
async def test_single_withouthost_slurm_scheduler() -> None:
    config = {"type": "slurm", "ssh_config": {}}
    with pytest.raises(TypeError):
        build(config)


@pytest.mark.anyio
async def test_single_sshsimplist_slurm_scheduler() -> None:
    config = {
        "type": "slurm",
        "ssh_config": {
            "hostname": "localhost",
        },
    }
    result = build(config)

    expected = SlurmScheduler(ssh_config=SshConnectConfig(hostname="localhost"))
    assert result == expected


@pytest.mark.anyio
async def test_single_sshcustom_slurm_scheduler() -> None:
    config = {
        "type": "slurm",
        "ssh_config": {
            "hostname": "localhost",
            "port": 10022,
            "username": "xenon",
            "password": "javagat",
        },
    }
    result = build(config)

    expected = SlurmScheduler(
        ssh_config=SshConnectConfig(  # noqa: S106
            hostname="localhost",
            port=10022,
            username="xenon",
            password="javagat",
        ),
    )
    assert result == expected
