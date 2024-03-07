from pathlib import Path
from typing import Protocol

from bartender.schedulers.abstract import JobDescription


class AbstractFileSystem(Protocol):
    """A file system interface."""

    def localize_description(
        self,
        description: JobDescription,
        entry: Path,
    ) -> JobDescription:
        """Make given job description local to this file system.

        Args:
            description: A job description.
            entry: The path to replace with the entry path of this file
                system. For example given a file system with entry path of
                /remote/jobs and given job_dir in job description of
                /local/jobs/myjobid and given entry of /local/jobs will return
                description with job dir /remote/jobs/myjobid .

        Returns:
            A job description local to this file system.
        """

    async def upload(self, src: JobDescription, target: JobDescription) -> None:
        """Uploads job directory of source description to job directory of target.

        Args:
            src: Local directory to copy from.
            target: Remote directory to copy to.
        """

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        """Download job directory of source description to job directory of target.

        Args:
            src: Remote directory to copy from.
            target: Local directory to copy to.
        """


    async def delete(self, description: JobDescription) -> None:
        """Delete job directory of description.

        Args:
            description: Remote directory to delete.
        """
        # after download or cancellation you might want to 
        # delete the remote job directory

    async def close(self) -> None:
        """Close filesystem."""
