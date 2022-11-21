from pathlib import Path

import pytest
from yaml import safe_dump

from bartender.config import build, parse
from bartender.destinations import Destination
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler
from bartender.settings import AppSetting

@pytest.mark.anyio
async def test_build_minimal(tmp_path: Path):
    file = tmp_path / "config.yaml"
    input = {
        "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
        "destinations": {},
    }
    with file.open("w") as f:
        safe_dump(input, f)

    result = build(file)

    expected = {
        "applications": {"app1": AppSetting(command="echo", config="/etc/passwd")},
        "destinations": {
            "": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem())
        },
    }
    assert result == expected


@pytest.mark.parametrize(
    "test_input",
    [
        ({}),
        ({"applications": {}}),
        ({"destinations": {}}),
    ],
)
def test_parse_keyerrors(test_input):
    with pytest.raises(KeyError):
        parse(test_input)

@pytest.mark.anyio
async def test_parse_single_destination():
    input = {
        "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
        "destinations": {
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
        },
    }

    result = parse(input)

    expected = {
        "applications": {"app1": AppSetting(command="echo", config="/etc/passwd")},
        "destinations": {
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
            )
        },
    }
    assert result == expected
