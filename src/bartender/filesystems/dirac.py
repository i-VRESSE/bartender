from pathlib import Path
from typing import Literal

from DIRAC import initialize
from DIRAC.DataManagementSystem.Client.DataManager import DataManager
from pydantic import BaseModel

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription


class DiracFileSystemConfig(BaseModel):
    """Configuration for DIRAC file system.

    Args:
        lfn_root: Location on grid storage where files of jobs can be stored. Used to
            localize description.
        storage_element: Storage element for lfn_root.
    """

    lfn_root: str
    storage_element: str
    type: Literal["dirac"] = "dirac"


# TODO make proper async with loop.run_in_executor


class DiracFileSystem(AbstractFileSystem):
    """Interact with DIRAC storage elements."""

    def __init__(
        self,
        config: DiracFileSystemConfig,
    ):
        """Constructor.

        Args:
            config: The config.
        """
        self.lfn_root = config.lfn_root
        self.storage_element = config.storage_element
        # TODO make sure initialize is only called once per process
        initialize()
        self.dm = DataManager()

    def localize_description(
        self,
        description: JobDescription,
        entry: Path,
    ) -> JobDescription:
        """Make given job description local to this file system.

        Args:
            description: A job description.
            entry: The path to replace with the entry path of this file system. For
                example given a file system with entry path of /remote/jobs and given
                job_dir in job description of /local/jobs/myjobid and given entry of
                /local/jobs will return description with job dir /remote/jobs/myjobid .

        Returns:
            A job description local to this file system.
        """
        localized_desciption = description.copy()
        localized_desciption.job_dir = self.lfn_root / Path(
            description.job_dir,
        ).relative_to(entry)
        return localized_desciption

    async def upload(self, src: JobDescription, target: JobDescription) -> None:
        """Uploads job directory of source description to job directory of target.

        Args:
            src: Local directory to copy from.
            target: Remote directory to copy to.

        Raises:
            RuntimeError: When upload failed.
        """
        # TODO dirac does not put recursive dir
        # so create and put archive of src.job_dir
        result = self.dm.putAndRegister(
            lfn=target.job_dir,
            fileName=src.job_dir,
            diracSE=self.storage_element,
        )
        if not result["OK"]:
            raise RuntimeError(result["Message"])

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        """Download job directory of source description to job directory of target.

        Args:
            src: Remote directory to copy from.
            target: Local directory to copy to.

        Raises:
            RuntimeError: When download failed.
        """
        # TODO dirac does not get recursive dir
        # so get archive of src.job_dir and unpack
        # TODO or use DIRAC.Interfaces.API.Dirac.Dirac.
        # getOutputSandbox(..., unpack=True)?
        result = self.dm.getFile(src.job_dir, target.job_dir)
        if not result["OK"]:
            raise RuntimeError(result["Message"])

    def close(self) -> None:
        """Close filesystem."""
