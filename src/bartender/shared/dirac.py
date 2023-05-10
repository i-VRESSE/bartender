import asyncio
import logging
from subprocess import CalledProcessError  # noqa: S404 security implications OK
from typing import Optional, Tuple

from DIRAC import gLogger, initialize
from DIRAC.Core.Security.ProxyInfo import getProxyInfo

from bartender.shared.dirac_config import ProxyConfig

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
    """
    # TODO use Python to create and renew proxy instead of subprocess call
    cmd = _proxy_init_command(config)
    logger.warning(f"Running command: {cmd}")
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdin = None
    if config.password:
        stdin = config.password.encode()
    stdout, stderr = await process.communicate(stdin)
    if process.returncode:
        raise CalledProcessError(process.returncode, cmd, stderr=stderr, output=stdout)


def _proxy_init_command(config: ProxyConfig) -> str:
    parts = ["dirac-proxy-init"]
    if config.valid:
        parts.append(f"-v {config.valid}")
    if config.cert:
        parts.append(f"-C {config.cert}")
    if config.key:
        parts.append(f"-K {config.key}")
    if config.group:
        parts.append(f"-g {config.group}")
    if config.password:
        parts.append("-p")
    return " ".join(parts)


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
        initialize(require_auth=False)
        gLogger.setLevel(config.log_level)
        task = asyncio.create_task(renew_proxy_task(config))
        renewer = (task, config)  # noqa: WPS442 simpler then singleton
        return
    if renewer[1] != config:
        raise ValueError("Can only have one unique proxy config")


async def teardown_proxy_renewer() -> None:
    """Tear down the renewer for the DIRAC proxy."""
    global renewer  # noqa: WPS420 simpler then singleton
    if renewer:
        task = renewer[0]
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        renewer = None  # noqa: WPS442 simpler then singleton
