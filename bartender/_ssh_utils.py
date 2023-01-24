from typing import Optional, TypedDict

from asyncssh import SSHClientConnection, connect


class SshConnectConfig(TypedDict):
    """Configuration for ssh connection."""

    hostname: str
    port: Optional[int]
    username: Optional[str]
    password: Optional[str]


async def ssh_connect(config: SshConnectConfig) -> SSHClientConnection:
    """Connect to a host using SSH.

    :param config: Configuration.
    :return: The connection.
    """
    conn_vargs = {
        # disable server host key validation
        "known_hosts": None,
    }
    if config["password"] is not None:
        conn_vargs["agent_path"] = None

    return await connect(
        host=config["hostname"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        **conn_vargs,
    )
