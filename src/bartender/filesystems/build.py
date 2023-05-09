from typing import Union

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.dirac_config import DiracFileSystemConfig
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.filesystems.sftp import SftpFileSystem, SftpFileSystemConfig
from bartender.shared.dirac_config import DIRAC_INSTALLED

FileSystemConfig = Union[
    LocalFileSystemConfig,
    SftpFileSystemConfig,
    DiracFileSystemConfig,
]


def build(config: FileSystemConfig) -> AbstractFileSystem:
    """Build a file system from a configuration.

    Args:
        config: The configuration

    Raises:
        ValueError: When unknown config is given.

    Returns:
        A file system instance.
    """
    if isinstance(config, LocalFileSystemConfig):
        return LocalFileSystem()
    if isinstance(config, SftpFileSystemConfig):
        return SftpFileSystem(config)
    if isinstance(config, DiracFileSystemConfig):
        if DIRAC_INSTALLED:
            from bartender.filesystems.dirac import (  # noqa: WPS433 is optional import
                DiracFileSystem,
            )

            return DiracFileSystem(config)
        raise ValueError("DIRAC package is not installed")
    raise ValueError(f"Unknown filesystem, recieved config is {config}")
