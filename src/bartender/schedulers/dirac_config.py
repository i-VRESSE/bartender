from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

from bartender.shared.dirac_config import ProxyConfig


class DiracSchedulerConfig(BaseModel):
    """Configuration for DIRAC scheduler.

    Args:
        apptainer_image: Path on cvmfs to apptainer image.
             Will run application command inside apptainer image.
        storage_element: Storage element to upload output files to.
        proxy: Proxy configuration.
    """

    type: Literal["dirac"] = "dirac"
    apptainer_image: Optional[Path] = None
    storage_element: str
    proxy: ProxyConfig = ProxyConfig()
