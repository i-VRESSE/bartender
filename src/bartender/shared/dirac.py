import asyncio
import logging
import shutil
from pathlib import Path
from subprocess import CalledProcessError  # noqa: S404 security implications OK
from typing import Optional, Tuple

from DIRAC import gLogger, initialize
from DIRAC.Core.Security.ProxyInfo import getProxyInfo
from DIRAC.Core.Utilities.exceptions import DIRACInitError

from bartender.shared.dirac_config import MyProxyConfig, ProxyConfig

logger = logging.getLogger(__file__)


def get_time_left_on_proxy() -> int:
    """
    Get the time left on the current proxy.

    Returns:
        The time left on the current proxy in seconds.

    Raises:
        ValueError: If failed to get proxy info.
    """
    result = getProxyInfo()
    if not result["OK"]:
        raise ValueError(f'Failed to get proxy info {result["Message"]}')
    return result["Value"]["secondsLeft"]


async def proxy_init(config: ProxyConfig) -> None:
    """Create or renew DIRAC proxy.

    Args:
        config: How to create a new proxy.

    Raises:
        CalledProcessError: If failed to create proxy.

    Returns:
        Nothing
    """
    if config.myproxy:
        return await myproxy_init(config)
    cmd = _proxy_init_command(config)
    logger.warning(f"Running command: {cmd}")
    process = await asyncio.create_subprocess_exec(
        cmd.pop(0),
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(
        config.password.encode() if config.password else None,
    )
    if process.returncode:
        raise CalledProcessError(process.returncode, cmd, stderr=stderr, output=stdout)


def _proxy_init_command(config: ProxyConfig) -> list[str]:
    parts = ["dirac-proxy-init"]
    if config.valid:
        parts.extend(["-v", config.valid])
    if config.cert:
        parts.extend(["-C", config.cert])
    if config.key:
        parts.extend(["-K", config.key])
    if config.group:
        parts.extend(["-g", config.group])
    if config.password:
        parts.append("-p")
    return parts


async def renew_proxy_task(config: ProxyConfig) -> None:
    """Task that makes sure the proxy is renewed when it is close to expiring.

    Args:
        config: How to create a new proxy.

    """
    while True:  # noqa: WPS457 should run lifetime of app
        time_left = await make_valid_dirac_proxy(config)
        await asyncio.sleep(time_left - config.min_life)


async def make_valid_dirac_proxy(config: ProxyConfig) -> int:
    """Make valid dirac proxy.

    Args:
        config: How to create a new proxy.

    Returns:
        The time left on the current proxy in seconds.
    """
    try:
        time_left = get_time_left_on_proxy()
    except ValueError:
        # if time left failed then create proxy
        await proxy_init(config)
        time_left = get_time_left_on_proxy()
    if time_left <= config.min_life:
        await proxy_init(config)
    return time_left


Renewer = Tuple[asyncio.Task[None], ProxyConfig]
renewer: Optional[Renewer] = None


def setup_proxy_renewer(config: ProxyConfig) -> None:
    """Set up a renewer for the DIRAC proxy.

    Args:
        config: How to create a new proxy.

    Raises:
        ValueError: If there is already a renewer with a different config.
    """
    global renewer  # noqa: WPS420 simpler then singleton
    if renewer is None:
        try:
            initialize()
        except DIRACInitError:
            logger.warning("DIRAC proxy not initialized, initializing")
            asyncio.run(proxy_init(config))
            initialize()
        gLogger.setLevel(config.log_level)
        task = asyncio.create_task(renew_proxy_task(config))
        renewer = (task, config)  # noqa: WPS442 simpler then singleton
        return
    if renewer[1] != config:
        raise ValueError(
            f"Can only have one unique proxy config. Old:{renewer[1]}, new: {config}",
        )


async def teardown_proxy_renewer() -> None:
    """Tear down the renewer for the DIRAC proxy."""
    global renewer  # noqa: WPS420 simpler then singleton
    if renewer:
        task = renewer[0]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        renewer = None  # noqa: WPS442 simpler then singleton


async def myproxy_init(config: ProxyConfig) -> None:
    """
    Create or renew proxy using MyProxy server.

    Args:
        config: The MyProxy configuration.

    Raises:
        ValueError: If no MyProxy configuration is provided.
    """
    if config.myproxy is None:
        raise ValueError("No myproxy configuration")

    # myproxy-logon \
    # --pshost config.pshost \
    # --proxy_lifetime config.proxy_lifetime \
    # --username config.username \
    # --out tmprfcfile \
    # --stdin_pass \
    # < config.password_file
    await myproxy_logon(config.myproxy)
    # cp tmprfcfile proxyfile
    await shutil.copy(config.myproxy.proxy_rfc, config.myproxy.proxy)
    # dirac-admin-proxy-upload -d -P tmprfcfile
    await proxy_upload(config.myproxy.proxy)
    # then check that proxy is valid and has time left
    get_time_left_on_proxy()


async def myproxy_logon(config: MyProxyConfig) -> None:
    """
    Log in to MyProxy server using the provided configuration.

    Args:
        config: The configuration object containing the necessary parameters.

    Raises:
        CalledProcessError: If the MyProxy logon process returns a non-zero exit code.

    Returns:
        None
    """
    password = config.password_file.read_bytes()
    cmd = [
        "myproxy-logon",
        "--pshost",
        config.pshost,
        "--proxy_lifetime",
        config.proxy_lifetime,
        "--username",
        config.username,
        "--out",
        str(config.proxy_rfc),
        "--stdin_pass",
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(
        password,
    )
    if process.returncode:
        raise CalledProcessError(process.returncode, cmd, stderr=stderr, output=stdout)


async def proxy_upload(proxy: Path) -> None:
    """
    Uploads the given proxy file using dirac-admin-proxy-upload command.

    Args:
        proxy: The path to the proxy file.

    Raises:
        CalledProcessError: If the subprocess returns a non-zero exit code.

    Returns:
        None
    """
    cmd = ["dirac-admin-proxy-upload", "-d", "-P", str(proxy)]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode:
        raise CalledProcessError(process.returncode, cmd, stderr=stderr, output=stdout)
