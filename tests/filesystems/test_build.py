from bartender.filesystems.build import build
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.filesystems.sftp import SftpFileSystem, SftpFileSystemConfig
from bartender.shared.ssh import SshConnectConfig


def test_local() -> None:
    config = LocalFileSystemConfig()

    result = build(config)

    expected = LocalFileSystem()
    assert result == expected


def test_sftp() -> None:
    config = SftpFileSystemConfig(ssh_config=SshConnectConfig(hostname="localhost"))

    result = build(config)

    expected = SftpFileSystem(config)
    assert result == expected
