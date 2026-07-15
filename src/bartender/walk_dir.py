from collections.abc import AsyncIterable, Callable
from datetime import datetime
from os import DirEntry, walk
from pathlib import Path
from stat import S_IFREG
from typing import Optional, Union

from aiofiles import open
from aiofiles.os import scandir, stat, wrap
from pydantic import BaseModel
from stream_zip import ZIP_32, AsyncMemberFile


class DirectoryItem(BaseModel):
    """An entry in a directory."""

    name: str
    path: Path
    is_dir: bool
    is_file: bool
    children: Optional[list["DirectoryItem"]] = None


async def walk_dir(
    path: Union[Path, DirEntry[str]],
    root: Path,
    max_depth: int = 1,
) -> DirectoryItem:
    """Traverse job dir returning the file names and directory names inside.

    Args:
        path: Path relative to root.
        root: The starting path.
        max_depth: Number of directories to traverse into.

    Returns:
        A tree of directory items.
    """
    is_dir = path.is_dir()
    rpath = Path(path).relative_to(root)
    item = DirectoryItem(
        name=rpath.name,
        path=rpath,
        is_dir=is_dir,
        is_file=path.is_file(),
    )
    if is_dir:
        current_depth = len(rpath.parts)
        if current_depth < max_depth:
            children = [
                await walk_dir(sub_entry, root, max_depth)
                for sub_entry in await scandir(path)
            ]
            if children:
                item.children = sorted(children, key=lambda entry: entry.name)
    return item


async_walk = wrap(walk)

WalkFilter = Callable[[str], bool]


def exclude_filter(excludes: list[str]) -> WalkFilter:
    """Create a filter that excludes paths based on a list.

    Args:
        excludes: List of patterns to exclude.

    Returns:
        A function that takes a path and returns True if it should be included.
    """
    if not excludes:
        return lambda _: True
    return lambda path: not any(pattern in path for pattern in excludes)


chunk_size = 1048576  # 1Mb
owner_read_only_file_mode = 0o400
read_only_file_mode = S_IFREG | owner_read_only_file_mode


async def _yield_file_contents(name: Path) -> AsyncIterable[bytes]:
    async with open(name, "rb") as handle:
        while chunk := await handle.read(chunk_size):
            yield chunk


async def _yield_file(path: Path, rpath: str) -> AsyncMemberFile:
    stats = await stat(path)
    return (
        rpath,
        datetime.fromtimestamp(stats.st_mtime),
        read_only_file_mode,
        ZIP_32,
        _yield_file_contents(path),
    )


async def walk_dir_generator(  # noqa: WPS231
    job_dir: Path,
    wfilter: WalkFilter = lambda _: True,
) -> AsyncIterable[AsyncMemberFile]:
    """Walk a directory and yield its files.

    Can be used as input for stream_zip.async_stream_zip

    Args:
        job_dir: The job directory.
        wfilter: A function that takes a path and returns True if it should be included.

    Yields:
        Tuple of file name, m_time, mode, method, file.
    """
    for root, _, files in await async_walk(job_dir):
        if not wfilter(str(Path(root).relative_to(job_dir))):
            continue
        for file in files:
            path = Path(root) / file
            rpath = str(path.relative_to(job_dir))
            if not wfilter(rpath):
                continue
            yield await _yield_file(path, rpath)
