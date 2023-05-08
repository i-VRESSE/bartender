from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel


class DiracSchedulerConfig(BaseModel):
    """Configuration for DIRAC scheduler.

    Args:
        apptainer_image: Path on cvmfs to apptainer image.
             Will run application command inside apptainer image.
        storage_element: Storage element to upload output files to.
    """

    type: Literal["dirac"] = "dirac"
    apptainer_image: Optional[Path] = None
    # TODO dedup storage element here and in filesystem config
    storage_element: str
