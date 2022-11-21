from pathlib import Path
from typing import Any

import pytest
from yaml import safe_dump as yaml_dump

from bartender._ssh_utils import SshConnectConfig
from bartender.config import ApplicatonConfiguration, Config, build_config, parse_config
from bartender.destinations import Destination
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender.schedulers.memory import MemoryScheduler
from bartender.schedulers.runner import SshCommandRunner
from bartender.schedulers.slurm import SlurmScheduler


@pytest.mark.anyio
async def test_build_minimal(tmp_path: Path) -> None:
    file = tmp_path / "config.yaml"
    config = {
        "applications": {"app1": {"command": "echo", "config": "/etc/passwd"}},
        "destinations": {},
    }
    with file.open("w") as handle:
        yaml_dump(config, handle)

    result = build_config(file)

    expected = Config(
        applications={
            "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
        },
        destinations={
            "": Destination(scheduler=MemoryScheduler(), filesystem=LocalFileSystem()),
        },
    )
    assert result == expected


@pytest.mark.parametrize(
    "test_input",
    [
        ({}),
        ({"applications": {}}),
        ({"destinations": {}}),
    ],
)
def test_parse_keyerrors(test_input: Any) -> None:
    with pytest.raises(KeyError):
        parse_config(test_input)


@pytest.mark.anyio
async def test_parse_single_destination() -> None:
    config = {
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

    result = parse_config(config)

    expected = Config(
        applications={
            "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
        },
        destinations={
            "dest2": Destination(
                scheduler=SlurmScheduler(
                    runner=SshCommandRunner(
                        config=SshConnectConfig(
                            hostname="localhost",
                        ),
                    ),
                    partition="mypartition",
                ),
                filesystem=SftpFileSystem(
                    config=SshConnectConfig(
                        hostname="localhost",
                    ),
                    entry=Path("/scratch/jobs"),
                ),
            ),
        },
    )
    assert result == expected
