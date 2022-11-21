from pathlib import Path
from typing import Any

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.local import LocalFileSystem
from bartender.filesystems.sftp import SftpFileSystem
from bartender._ssh_utils import SshConnectConfig

def build(config: Any) -> AbstractFileSystem:
    if config is None:
        return LocalFileSystem()
    if "type" not in config:
        raise KeyError("File system without type")
    if config["type"] == 'local':
        return LocalFileSystem()
    if config['type'] == 'sftp':
        if 'config' not in config:
            raise KeyError("Sftp file system without SSH connection configuration.")      
        sshconfig = SshConnectConfig(**config['config'])
        entry = Path('/')
        if 'entry' in config:
            entry = Path(config['entry'])
        return SftpFileSystem(sshconfig, entry)
    else:
        raise ValueError(f'File system with type {config["type"]} is unknown')
