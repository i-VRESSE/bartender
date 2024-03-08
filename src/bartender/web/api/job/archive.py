from pathlib import Path
from typing import Literal, Optional, Type, Union

from fs.copy import copy_fs
from fs.osfs import OSFS
from fs.tarfs import TarFS
from fs.walk import Walker
from fs.zipfs import ZipFS

from bartender.async_utils import async_wrap

ArchiveFormat = Literal[".zip", ".tar", ".tar.xz", ".tar.gz", ".tar.bz2"]


async def create_archive(
    src_dir: Path,
    exclude: Optional[list[str]],
    exclude_dirs: Optional[list[str]],
    archive_format: ArchiveFormat,
    archive_fn: str,
) -> None:
    """Creates an archive of the specified directory.

    Args:
        src_dir: The path to the source directory.
        exclude : A list of patterns to exclude from the archive.
        exclude_dirs: A list of directory names to exclude from the archive.
        archive_format: Format to use for archive.
        archive_fn: The filename of the archive.
    """
    dst_fs = _map_archive_format(archive_format)
    with (  # noqa: WPS316
        OSFS(str(src_dir)) as src,
        dst_fs(archive_fn, write=True) as dst,
    ):
        await async_wrap(copy_fs)(
            src,
            dst,
            walker=Walker(exclude=exclude, exclude_dirs=exclude_dirs),
        )


def _map_archive_format(
    archive_format: ArchiveFormat,
) -> Union[Type[ZipFS], Type[TarFS]]:
    if archive_format == ".zip":
        return ZipFS
    return TarFS
