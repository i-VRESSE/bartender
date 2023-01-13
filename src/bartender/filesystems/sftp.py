from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from asyncssh import SSHClientConnection

from bartender.filesystems.abstract import AbstractFileSystem
from bartender.schedulers.abstract import JobDescription
from bartender.ssh_utils import SshConnectConfig, ssh_connect


@dataclass
class SftpFileSystemConfig:
    """Configuration for SFTP file system.

    :param ssh_config: SSH connection configuration.
    :param entry: The entry directory. Used to localize description.
    """

    ssh_config: SshConnectConfig
    entry: Path = Path("/")
    type: Literal["sftp"] = "sftp"


class SftpFileSystem(AbstractFileSystem):
    """Remote filesystem using SFTP protocol."""

    def __init__(
        self,
        config: SftpFileSystemConfig,
    ):
        """Constructor.

        :param config: The config.
        """
        self.entry = config.entry
        self.ssh_config = config.ssh_config
        self.conn: Optional[SSHClientConnection] = None

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
        localized_desciption.job_dir = self.entry / Path(
            description.job_dir,
        ).relative_to(entry)
        return localized_desciption

    async def upload(self, src: JobDescription, target: JobDescription) -> None:
        """Uploads job directory of source description to job directory of target.

        :param src: Local directory to copy from.
        :param target: Remote directory to copy to.
        """
        if self.conn is None:
            self.conn = await ssh_connect(self.ssh_config)
        async with self.conn.start_sftp_client() as sftp:
            localpaths = [str(src.job_dir)]
            remotepath = str(target.job_dir)
            await sftp.put(localpaths, remotepath, recurse=True)

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        """Download job directory of source description to job directory of target.

        :param src: Remote directory to copy from.
        :param target: Local directory to copy to.
        """
        if self.conn is None:
            self.conn = await ssh_connect(self.ssh_config)
        async with self.conn.start_sftp_client() as sftp:
            # target.job_dir.parent is used
            # so /remote/jobid/output becomes /local/jobid/output,
            # otherwise it would be /local/jobid/jobid/output
            localpaths = [str(src.job_dir)]
            remotepath = str(target.job_dir.parent)
            await sftp.get(localpaths, remotepath, recurse=True)

    def close(self) -> None:
        """Close SSH connection."""
        if self.conn:
            self.conn.close()

    # TODO add delete(description),
    # after download you might want to delete the remote job dir

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SftpFileSystem)
            and str(self.entry) == str(other.entry)
            and self.ssh_config == other.ssh_config
        )

    def __repr__(self) -> str:
        return f"SftpFileSystem(ssh_config={self.ssh_config}, entry={self.entry})"
