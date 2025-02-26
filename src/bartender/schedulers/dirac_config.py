from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from bartender.shared.dirac_config import ProxyConfig


class DiracSchedulerConfig(BaseModel):
    """Configuration for DIRAC scheduler.

    Args:
        apptainer_image: Path on cvmfs or grid storage to apptainer image.
             When set will run application command inside apptainer image.
             Image can also be on grid storage,
             it will then be downloaded to current directory first.
        storage_element: Storage element to upload output files to.
        proxy: Proxy configuration.
    """

    type: Literal["dirac"] = "dirac"
    apptainer_image: Optional[Path] = None
    storage_element: str
    proxy: ProxyConfig = ProxyConfig()
