import pytest

from bartender.schedulers.build import assemble
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import LocalCommandRunner, SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


def test_no_schedulers_key():
    config = {}
    with pytest.raises(ValueError):
        assemble(config)


def test_zero_schedulers():
    config = {"schedulers": []}
    with pytest.raises(ValueError):
        assemble(config)


def test_single_typeless_scheduler():
    config = {"schedulers": {"local": {}}}
    with pytest.raises(ValueError):
        assemble(config)


def test_single_unknown_scheduler():
    config = {"schedulers": {"local": {type: "unknown"}}}
    with pytest.raises(ValueError):
        assemble(config)


@pytest.mark.anyio
async def test_single_memory_scheduler():
    config = {"schedulers": {"local": {"type": "memory"}}}
    result = assemble(config)

    expected = {"local": MemoryScheduler()}
    assert result == expected


@pytest.mark.anyio
async def test_single_custom_memory_scheduler():
    config = {"schedulers": {"local": {"type": "memory", "slots": 4}}}
    result = assemble(config)

    expected = {"local": MemoryScheduler(slots=4)}
    assert result == expected


@pytest.mark.anyio
async def test_single_localsimplist_slurm_scheduler():
    config = {"schedulers": {"slurm": {"type": "slurm"}}}
    result = assemble(config)

    expected = {"slurm": SlurmScheduler(LocalCommandRunner())}
    assert result == expected


@pytest.mark.anyio
async def test_single_localcustom_slurm_scheduler():
    config = {
        "schedulers": {
            "slurm": {
                "type": "slurm",
                "partition": "mypartition",
                "time": 60,
                "extra_options": ["--nodes 1"],
            }
        }
    }
    result = assemble(config)

    expected = {
        "slurm": SlurmScheduler(
            runner=LocalCommandRunner(),
            partition="mypartition",
            time=60,
            extra_options=["--nodes 1"],
        )
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_typelessrunner_slurm_scheduler():
    config = {"schedulers": {"slurm": {"type": "slurm", "runner": {}}}}
    with pytest.raises(ValueError):
        assemble(config)


@pytest.mark.anyio
async def test_single_unknownrunner_slurm_scheduler():
    config = {"schedulers": {"slurm": {"type": "slurm", "runner": {"type": "unknown"}}}}
    with pytest.raises(ValueError):
        assemble(config)


@pytest.mark.anyio
async def test_single_withouthost_slurm_scheduler():
    config = {"schedulers": {"slurm": {"type": "slurm", "runner": {"type": "ssh"}}}}
    with pytest.raises(ValueError):
        assemble(config)


@pytest.mark.anyio
async def test_single_sshsimplist_slurm_scheduler():
    config = {
        "schedulers": {
            "slurm": {
                "type": "slurm",
                "runner": {
                    "type": "ssh",
                    "hostname": "localhost",
                },
            }
        }
    }
    result = assemble(config)

    expected = {
        "slurm": SlurmScheduler(SshCommandRunner(config={"hostname": "localhost"}))
    }
    assert result == expected


@pytest.mark.anyio
async def test_single_sshcustom_slurm_scheduler():
    config = {
        "schedulers": {
            "slurm": {
                "type": "slurm",
                "runner": {
                    "type": "ssh",
                    "hostname": "localhost",
                    "port": 10022,
                    "username": "xenon",
                    "password": "javagat",
                },
            }
        }
    }
    result = assemble(config)

    expected = {
        "slurm": SlurmScheduler(
            SshCommandRunner(
                config={
                    "hostname": "localhost",
                    "port": 10022,
                    "username": "xenon",
                    "password": "javagat",
                }
            )
        )
    }
    assert result == expected
