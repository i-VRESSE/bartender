import pkgutil
from typing import Optional

from pydantic import BaseModel

DIRAC_INSTALLED = (
    pkgutil.find_loader("DIRAC") is not None
)  # noqa: WPS462 sphinx understands
"""True if DIRAC package is installed, False otherwise."""  # noqa: E501, WPS322, WPS428 sphinx understands


class ProxyConfig(BaseModel):
    """Configuration for DIRAC proxy.

    Args:
        cert: The path to the user's DIRAC proxy certificate.
        key: The path to the user's private key file.
        group: The name of the DIRAC group to use.
        valid: Valid HH:MM for the proxy. By default is 24 hours.
    """
    cert: Optional[str] = None
    key: Optional[str] = None
    group: Optional[str] = None
    valid: str = '24:00'
