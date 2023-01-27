from typing import Union

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.local import LocalFileSystem, LocalFileSystemConfig
from bartender.filesystems.sftp import SftpFileSystem, SftpFileSystemConfig

FileSystemConfig = Union[LocalFileSystemConfig, SftpFileSystemConfig]


def build(config: FileSystemConfig) -> AbstractFileSystem:
    """Build a file system from a configuration.

    :param config: The configuration
    :raises ValueError: When unknown config is given.
    :return: A file system instance.
    """
    if isinstance(config, LocalFileSystemConfig):
        return LocalFileSystem()
    if isinstance(config, SftpFileSystemConfig):
        return SftpFileSystem(config)
    raise ValueError(f"Unknown filesystem, recieved config is {config}")
