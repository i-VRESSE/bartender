import pkgutil
from typing import Literal, Optional

from pydantic import BaseModel

DIRAC_INSTALLED = (
    pkgutil.find_loader("DIRAC") is not None
)  # noqa: WPS462 sphinx understands
"""True if DIRAC package is installed, False otherwise."""  # noqa: E501, WPS322, WPS428 sphinx understands


# Levels from
# https://github.com/DIRACGrid/DIRAC/blob/959bf09c77bc64d54db7159b17878a362dc13b52/src/DIRAC/FrameworkSystem/private/standardLogging/LogLevels.py#L81
LogLevel = Literal[
    "DEBUG",
    "VERBOSE",
    "INFO",
    "WARN",
    "NOTICE",
    "ERROR",
    "ALWAYS",
    "FATAL",
]


class ProxyConfig(BaseModel):
    """Configuration for DIRAC proxy.

    Args:
        cert: The path to the user's DIRAC proxy certificate.
        key: The path to the user's private key file.
        group: The name of the DIRAC group to use.
        valid: Valid HH:MM for the proxy. By default is 24 hours.
        password: The password for the private key file.
        min_life: If proxy has less than this many seconds left, renew it.
            Default 30 minutes.
        log_level: The log level for the DIRAC logger. Default INFO.
    """

    cert: Optional[str] = None
    key: Optional[str] = None
    group: Optional[str] = None
    valid: Optional[str] = None
    password: Optional[str] = None
    min_life: int = 1800
    log_level: LogLevel = "INFO"
