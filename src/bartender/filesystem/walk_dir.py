from os import DirEntry
from pathlib import Path
from typing import Optional, Union

from aiofiles.os import scandir
from pydantic import BaseModel


class DirectoryItem(BaseModel):
    """An entry in a directory."""

    name: str
    path: Path
    is_dir: bool
    is_file: bool
    children: Optional[list["DirectoryItem"]]


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
