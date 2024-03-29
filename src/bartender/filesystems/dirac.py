import logging
from pathlib import Path
from shutil import make_archive, unpack_archive
from typing import Any

from aiofiles.tempfile import TemporaryDirectory
from DIRAC.DataManagementSystem.Client.DataManager import DataManager

from bartender.async_utils import async_wrap
from bartender.filesystems.abstract import AbstractFileSystem
from bartender.filesystems.dirac_config import DiracFileSystemConfig
from bartender.schedulers.abstract import JobDescription
from bartender.shared.dirac import setup_proxy_renewer, teardown_proxy_renewer

logger = logging.getLogger(__file__)


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
        setup_proxy_renewer(config.proxy)
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

        A tar archive of the `src.job_dir` will be uploaded.
        The tar archive will be named `target.job_dir / input.tar`.

        Args:
            src: Local directory to copy from.
            target: Remote directory to copy to.
        """
        put = async_wrap(self.dm.putAndRegister)
        async with TemporaryDirectory(prefix="bartender-upload") as tmpdirname:
            archive_fn = await self._pack(src.job_dir, Path(tmpdirname))
            input_tar_on_grid = target.job_dir / archive_fn.name
            logger.warning(
                f"Uploading {archive_fn} to {input_tar_on_grid}"
                f"on {self.storage_element}",
            )
            result = await put(
                lfn=str(input_tar_on_grid),
                fileName=str(archive_fn),
                diracSE=self.storage_element,
            )
            _check_for_failure(result)

    async def download(self, src: JobDescription, target: JobDescription) -> None:
        """Download job directory of source description to job directory of target.

        A tar archive with name `src.job_dir / output.tar` will be downloaded.
        The tar archive will be unpacked to `target.job_dir`.

        Args:
            src: Remote directory to copy from.
            target: Local directory to copy to.
        """
        archive_base_fn = "output.tar"
        archive_fn_on_grid = Path(src.job_dir) / archive_base_fn
        async with TemporaryDirectory(prefix="bartender-upload") as tmpdirname:
            logger.warning(f"Downloading {archive_fn_on_grid} to {tmpdirname}")
            result = await async_wrap(self.dm.getFile)(
                str(archive_fn_on_grid),
                tmpdirname,
            )
            _check_for_failure(result)
            archive_fn_in_tmpdir = Path(tmpdirname) / archive_base_fn
            # TODO what happens if file in job_dir already exists?
            logger.warning(f"Unpacking {archive_fn_in_tmpdir} to {target.job_dir}")
            await async_wrap(unpack_archive)(archive_fn_in_tmpdir, target.job_dir)

    async def close(self) -> None:
        """Close filesystem."""
        await teardown_proxy_renewer()

    async def delete(self, description: JobDescription) -> None:
        """Delete job directory of description.

        Args:
            description: The job description.
        """
        result = await async_wrap(self.dm.cleanLogicalDirectory)(
            str(description.job_dir),
        )
        _check_for_failure(result)

    async def _pack(self, root_dir: Path, container_dir: Path) -> Path:
        archive_base_fn = container_dir / "input"
        archive_format = "tar"
        archive_fn = await async_wrap(make_archive)(
            archive_base_fn,
            archive_format,
            root_dir,
        )
        return Path(archive_fn)


def _check_for_failure(result: Any) -> None:
    if not result["OK"]:
        raise RuntimeError(result["Message"])
    if result["Value"]["Failed"]:
        # All dm method are for single lfn,
        # but failed is a dict with lfn as key
        # so pick the last value as the error message
        failures = result["Value"]["Failed"]
        fn, msg = list(failures.items()).pop()
        if "No such file or directory" in msg:
            raise FileNotFoundError(fn)
        raise RuntimeError(msg + fn)
