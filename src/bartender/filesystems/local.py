from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription


class LocalFileSystemConfig(BaseModel):
    """Configuration for local file system."""

    type: Literal["local"] = "local"


class LocalFileSystem(AbstractFileSystem):
    """File system operations on file system current Python process is running on."""

    def localize_description(
        self,
        description: JobDescription,
        entry: Path,
    ) -> JobDescription:
        """Make given job description local to this file system.

        Args:
            description: A job description.
            entry: The path to replace with the entry path of this file
                system. For example given a file system with entry path
                of /remote/jobs and given job_dir in job description of
                /local/jobs/myjobid and given entry of /local/jobs will
                return description with job dir /remote/jobs/myjobid .

        Returns:
            A job description local to this file system.
        """
        # TODO do something with entry argument?
        return description

    async def upload(
        self,
        src: JobDescription,
        target: JobDescription,
    ) -> None:
        """Uploads job directory of source description to job directory of target.

        Args:
            src: Local directory to copy from.
            target: Remote directory to copy to.
        """

    async def download(
        self,
        src: JobDescription,
        target: JobDescription,
    ) -> None:
        """Download job directory of source description to job directory of target.

        Args:
            src: Remote directory to copy from.
            target: Local directory to copy to.
        """

    def close(self) -> None:
        """Close filesystem."""

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LocalFileSystem)

    def __repr__(self) -> str:
        return "LocalFileSystem()"
