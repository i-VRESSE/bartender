from typing import Literal

from pydantic import BaseModel

from bartender.shared.dirac_config import ProxyConfig


class DiracFileSystemConfig(BaseModel):
    """Configuration for DIRAC file system.

    Args:
        lfn_root: Location on grid storage where files of jobs can be stored. Used to
            localize description.
        storage_element: Storage element for lfn_root.
        proxy: Proxy configuration.
    """

    type: Literal["dirac"] = "dirac"
    lfn_root: str
    storage_element: str
    proxy: ProxyConfig = ProxyConfig()
