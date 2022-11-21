from pathlib import Path
import pytest

from bartender.filesystems.build import build
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender._ssh_utils import SshConnectConfig


def test_none():
    result = build(None)
    expected = LocalFileSystem()
    assert result == expected


def test_emptydict():
    with pytest.raises(KeyError):
        build({})


def test_unknowntype():
    config = {"type": "unknown"}
    with pytest.raises(ValueError):
        build(config)


def test_local():
    config = {"type": "local"}
    result = build(config)

    expected = LocalFileSystem()
    assert result == expected


def test_sftp_withoutconfig():
    config = {"type": "sftp"}
    with pytest.raises(KeyError):
        build(config)


def test_sftp_simplest():
    config = {"type": "sftp", "config": {"hostname": "localhost"}}
    result = build(config)

    expected = SftpFileSystem(SshConnectConfig(hostname="localhost"))
    assert result == expected


def test_sftp_entry():
    config = {
        "type": "sftp",
        "config": {"hostname": "localhost"},
        "entry": "/scratch/jobs",
    }
    result = build(config)

    expected = SftpFileSystem(
        SshConnectConfig(hostname="localhost"), entry=Path("/scratch/jobs")
    )
    assert result == expected


def test_sftp_verbosist():
    config = {
        "type": "sftp",
        "config": {
            "hostname": "localhost",
            "port": 2222,
            "username": "someone",
            "password": "somepw",
        },
        "entry": "/scratch/jobs",
    }
    result = build(config)

    expected = SftpFileSystem(
        SshConnectConfig(
            hostname="localhost", port=2222, username="someone", password="somepw"
        ),
        entry=Path("/scratch/jobs"),
    )
    assert result == expected
