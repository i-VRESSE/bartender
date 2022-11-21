from pathlib import Path
from typing import Any

from bartender._ssh_utils import SshConnectConfig
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem


def build(config: Any) -> AbstractFileSystem:
    """Build a file system from a configuration.

    :param config: The configuration
    :raises KeyError: When a key is missing
    :raises ValueError: When a value is incorrect.
    :return: A file system instance.
    """
    if config is None:
        return LocalFileSystem()
    if "type" not in config:
        raise KeyError("File system without type")
    if config["type"] == "local":
        return LocalFileSystem()
    if config["type"] == "sftp":
        if "config" not in config:
            raise KeyError("Sftp file system without SSH connection configuration.")
        ssh_config = SshConnectConfig(**config["config"])
        entry_config = config.get("entry", "/")
        entry = Path(entry_config)
        return SftpFileSystem(ssh_config, entry)
    raise ValueError(f'File system with type {config["type"]} is unknown')
