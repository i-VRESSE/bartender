from pathlib import Path

import pytest

from bartender._ssh_utils import SshConnectConfig
from bartender.filesystems.build import build
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem


def test_none() -> None:
    result = build(None)
    expected = LocalFileSystem()
    assert result == expected


def test_emptydict() -> None:
    with pytest.raises(KeyError):
        build({})


def test_unknowntype() -> None:
    config = {"type": "unknown"}
    with pytest.raises(ValueError):
        build(config)


def test_local() -> None:
    config = {"type": "local"}
    result = build(config)

    expected = LocalFileSystem()
    assert result == expected


def test_sftp_withoutconfig() -> None:
    config = {"type": "sftp"}
    with pytest.raises(KeyError):
        build(config)


def test_sftp_simplest() -> None:
    config = {"type": "sftp", "ssh_config": {"hostname": "localhost"}}
    result = build(config)

    expected = SftpFileSystem(SshConnectConfig(hostname="localhost"))
    assert result == expected


def test_sftp_entry() -> None:
    config = {
        "type": "sftp",
        "ssh_config": {"hostname": "localhost"},
        "entry": "/scratch/jobs",
    }
    result = build(config)

    expected = SftpFileSystem(
        SshConnectConfig(hostname="localhost"),
        entry=Path("/scratch/jobs"),
    )
    assert result == expected


def test_sftp_verbosist() -> None:
    config = {
        "type": "sftp",
        "ssh_config": {
            "hostname": "localhost",
            "port": 2222,
            "username": "someone",
            "password": "somepw",
        },
        "entry": "/scratch/jobs",
    }
    result = build(config)

    expected = SftpFileSystem(
        SshConnectConfig(  # noqa: S106
            hostname="localhost",
            port=2222,
            username="someone",
            password="somepw",
        ),
        entry=Path("/scratch/jobs"),
    )
    assert result == expected
