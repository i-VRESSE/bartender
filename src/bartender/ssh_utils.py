from asyncssh import SSHClientConnection, connect
from asyncssh.misc import DefTuple
from pydantic import BaseModel


class SshConnectConfig(BaseModel):
    """Configuration for ssh connection.

    Attributes:
        usename: Username to connect with. When absent will use username of
            logged in user.
    """

    hostname: str
    port: DefTuple[int] = ()
    username: DefTuple[str] = ()
    password: DefTuple[str] = ()


async def ssh_connect(config: SshConnectConfig) -> SSHClientConnection:
    """Connect to a host using SSH.

    Args:
        config: Configuration.

    Returns:
        The connection.
    """
    conn_vargs = {
        # disable server host key validation
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
