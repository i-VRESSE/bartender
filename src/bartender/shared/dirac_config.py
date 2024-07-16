import pkgutil
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, FilePath

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


class MyProxyConfig(BaseModel):
    """Configuration for MyProxy server.

    Args:
        pshost: The hostname of the MyProxy server.
        username: Username for the delegated proxy
        proxy_lifetime: Lifetime of proxies delegated by the server
        password_file: The path to the file containing the password for the proxy.
        proxy_rfc: The path to the generated RFC proxy file.
        proxy: The path to the generated proxy file.
            This proxy file should be used submit and manage jobs.
    """

    pshost: str = "px.grid.sara.nl"
    username: str
    password_file: FilePath
    proxy_lifetime: str = "167:59"  # 7 days
    proxy_rfc: Path
    proxy: Path


class ProxyConfig(BaseModel):
    """Configuration for DIRAC proxy.

    Args:
        cert: The path to the user's DIRAC proxy certificate.
        key: The path to the user's private key file.
        group: The name of the DIRAC group to use.
        valid: How long proxy should be valid. Format HH:MM.
            By default is 24 hours.
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
    myproxy: Optional[MyProxyConfig] = None
