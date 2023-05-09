from typing import Literal

from pydantic import BaseModel

from bartender.shared.dirac_config import ProxyConfig


class DiracFileSystemConfig(BaseModel):
    """Configuration for DIRAC file system.

    Args:
        lfn_root: Location on grid storage where files of jobs can be stored. Used to
            localize description.
        storage_element: Storage element for lfn_root.
    """

    type: Literal["dirac"] = "dirac"
    # TODO remove defaults, defaults work for
    # ghcr.io/xenon-middleware/dirac:8.0.18 docker container
    lfn_root: str = "/tutoVO/user/c/ciuser/bartenderjobs"
    storage_element: str = "StorageElementOne"
    proxy: ProxyConfig = ProxyConfig()
