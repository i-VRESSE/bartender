import asyncio
import logging
from datetime import datetime, timedelta

from DIRAC import gLogger, initialize
from DIRAC.Core.Security.ProxyInfo import getProxyInfo

from bartender.shared.dirac_config import ProxyConfig

logger = logging.getLogger(__file__)


def throttle(seconds: float):
    """Throttle decorator to limit the frequency of function calls."""
    last_call = datetime.min

    def decorator(func):
        async def wrapper(*args, **kwargs):
            nonlocal last_call
            now = datetime.now()
            if now - last_call < timedelta(seconds=seconds):
                logger.warning(f"Not calling {func.__name__}, last call was too recent")
                return
            last_call = now
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class ProxyChecker:
    def __init__(self, config: ProxyConfig) -> None:
        self.config = config
        self.last_check = None
        # TODO make sure initialize is only called once per processeng instead of each time checker is created
        # TODO make sure proxy is initialized before calling `initialize()`
        initialize()
        gLogger.setLevel("debug")  # TODO remove

    def _info(self):
        result = getProxyInfo()
        if not result["OK"]:
            raise ValueError(f'Failed to get proxy info {result["Message"]}')
        logger.warning(f"Proxy info: {result['Value']}")
        return result["Value"]

    def _secondsLeft(self):
        return self._info()["secondsLeft"]

    @throttle(seconds=1800)
    async def check(self):
        """Make sure that the DIRAC proxy is valid."""
        # TODO check that there is a proxy, if not then create one
        # TODO Check that current proxy is expired or close to expiring
        logger.warning("Checking how many seconds the proxy has left")
        min_life = 1800
        seconds_left = self._secondsLeft()
        if seconds_left < min_life:
            logger.warning(
                f"Proxy almost expired, just {seconds_left}s left, renewing...",
            )
            # TODO use Python to create and renew proxy instead of subprocess call
            parts = []
            if self.config.valid:
                parts.append(f"-v {self.config.valid}")
            if self.config.cert:
                parts.append(f"-C {self.config.cert}")
            if self.config.key:
                parts.append(f"-K {self.config.key}")
            if self.config.group:
                parts.append(f"-g {self.config.group}")
            if self.config.password:
                parts.append(f"-p")
            cmd = f'dirac-proxy-init {" ".join(parts)}'
            logger.warning(f"Running command: {cmd}")
            process = await asyncio.create_subprocess_shell(cmd)
            if self.config.password:
                await process.communicate(self.config.password.encode())
            else:
                await process.communicate()
