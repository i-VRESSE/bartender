from pathlib import Path
from typing import Literal

from DIRAC.DataManagementSystem.Client.DataManager import DataManager
from pydantic import BaseModel

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription


class DiracFileSystemConfig(BaseModel):
    """Configuration for Dirac file system.

    :param lfn_root: Location on grid storage where files of jobs can be stored.
        Used to localize description.
    :param storage_element: Storage element for lfn_root.
    """

    lfn_root: str
    storage_element: str
    type: Literal["dirac"] = "dirac"


# TODO make proper async with loop.run_in_executor


class DiracFileSystem(AbstractFileSystem):
    """Interact with Dirac storage elements."""

    def __init__(
        self,
        config: DiracFileSystemConfig,
    ):
        """Constructor.

        :param config: The config.
        """
        self.lfn_root = config.lfn_root
        self.storage_element = config.storage_element
        self.dm = DataManager()

    def localize_description(
        self,
        description: JobDescription,
        entry: Path,
    ) -> JobDescription:
        """Make given job description local to this file system.

        :param description: A job description.
        :param entry: The path to replace with the entry path of this file system.
            For example given a file system with entry path of /remote/jobs
            and given job_dir in job description of /local/jobs/myjobid
            and given entry of /local/jobs
            will return description with job dir /remote/jobs/myjobid .
        :return: A job description local to this file system.
        """
        localized_desciption = description.copy()
        localized_desciption.job_dir = self.lfn_root / Path(
            description.job_dir,
        ).relative_to(entry)
        return localized_desciption

    async def upload(self, src: JobDescription, target: JobDescription) -> None:
        """Uploads job directory of source description to job directory of target.

        :param src: Local directory to copy from.
        :param target: Remote directory to copy to.
        """
        # TODO dirac does not put recursive dir
        # so create and put archive of src.job_dir
        self.dm.putAndRegister(
            lfn=target.job_dir,
            fileName=src.job_dir,
            diracSE=self.storage_element,
        )

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        """Download job directory of source description to job directory of target.

        :param src: Remote directory to copy from.
        :param target: Local directory to copy to.
        """
        # TODO dirac does not get recursive dir
        # so get archive of src.job_dir and unpack
        self.dm.getFile(src.job_dir, target.job_dir)

    def close(self) -> None:
        """Close filesystem."""
