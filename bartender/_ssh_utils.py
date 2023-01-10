from dataclasses import dataclass

from asyncssh import SSHClientConnection, connect
from asyncssh.misc import DefTuple


@dataclass
class SshConnectConfig:
    """Configuration for ssh connection."""

    hostname: str
    port: DefTuple[int] = ()
    username: DefTuple[str] = ()
    password: DefTuple[str] = ()


async def ssh_connect(config: SshConnectConfig) -> SSHClientConnection:
    """Connect to a host using SSH.

    :param config: Configuration.
    :return: The connection.
    """
    conn_vargs = {
        "known_hosts": None,
    }
    if config.password:
        # Do not use SSH agent when password is supplied.
        conn_vargs["agent_path"] = None

    return await connect(
        host=config.hostname,
        port=config.port,
        username=config.username,
        password=config.password,
        **conn_vargs,
    )
