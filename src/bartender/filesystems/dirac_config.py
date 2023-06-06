import re
from typing import Literal

from pydantic import BaseModel, validator

from bartender.shared.dirac_config import ProxyConfig


class DiracFileSystemConfig(BaseModel):
    """Configuration for DIRAC file system.

    Args:
        lfn_root: Location on grid storage where files of jobs can be stored. Used to
            localize description. 
            To stage output files the root should be located within the user's home directory.
            Home directory is formatted like `/<VO>/user/<initial>/<username>`.
        storage_element: Storage element for lfn_root.
        proxy: Proxy configuration.
    """

    type: Literal["dirac"] = "dirac"
    lfn_root: str
    storage_element: str
    proxy: ProxyConfig = ProxyConfig()

    @validator('lfn_root')
    def _validate_lfn_root(cls, v):
        pattern = r'^\/\w+\/user\/([a-zA-Z])\/\1\w+\/.*$'
        if not re.match(pattern, v):
            raise ValueError(f"{v} should match the format `/<VO>/user/<initial>/<username>/<whatever>`")
        return v
