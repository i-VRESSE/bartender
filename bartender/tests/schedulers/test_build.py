import pytest

from bartender.schedulers.build import build
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import LocalCommandRunner, SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


def test_single_typeless_scheduler():
    config = {}
    with pytest.raises(KeyError):
        build(config)


def test_single_unknown_scheduler():
    config = {type: "unknown"}
    with pytest.raises(ValueError):
        build(config)


@pytest.mark.anyio
async def test_single_memory_scheduler():
    config = {"type": "memory"}
    result = build(config)

    expected = MemoryScheduler()
    assert result == expected


@pytest.mark.anyio
async def test_single_custom_memory_scheduler():
    config = {"type": "memory", "slots": 4}
    result = build(config)

    expected = MemoryScheduler(slots=4)
    assert result == expected


@pytest.mark.anyio
async def test_single_localsimplist_slurm_scheduler():
    config = {"type": "slurm"}
    result = build(config)

    expected = SlurmScheduler(LocalCommandRunner())
    assert result == expected


@pytest.mark.anyio
async def test_single_localcustom_slurm_scheduler():
    config = {
        "type": "slurm",
        "partition": "mypartition",
        "time": 60,
        "extra_options": ["--nodes 1"],
    }
    result = build(config)

    expected = SlurmScheduler(
        runner=LocalCommandRunner(),
        partition="mypartition",
        time=60,
        extra_options=["--nodes 1"],
    )
    assert result == expected


@pytest.mark.anyio
async def test_single_typelessrunner_slurm_scheduler():
    config = {"type": "slurm", "runner": {}}
    with pytest.raises(ValueError):
        build(config)


@pytest.mark.anyio
async def test_single_unknownrunner_slurm_scheduler():
    config = {"type": "slurm", "runner": {"type": "unknown"}}
    with pytest.raises(ValueError):
        build(config)


@pytest.mark.anyio
async def test_single_withouthost_slurm_scheduler():
    config = {"type": "slurm", "runner": {"type": "ssh"}}
    with pytest.raises(ValueError):
        build(config)


@pytest.mark.anyio
async def test_single_sshsimplist_slurm_scheduler():
    config = {
        "type": "slurm",
        "runner": {
            "type": "ssh",
            "hostname": "localhost",
        },
    }
    result = build(config)

    expected = SlurmScheduler(SshCommandRunner(config={"hostname": "localhost"}))
    assert result == expected


@pytest.mark.anyio
async def test_single_sshcustom_slurm_scheduler():
    config = {
        "type": "slurm",
        "runner": {
            "type": "ssh",
            "hostname": "localhost",
            "port": 10022,
            "username": "xenon",
            "password": "javagat",
        },
    }
    result = build(config)

    expected = SlurmScheduler(
        SshCommandRunner(
            config={
                "hostname": "localhost",
                "port": 10022,
                "username": "xenon",
                "password": "javagat",
            }
        )
    )
    assert result == expected
