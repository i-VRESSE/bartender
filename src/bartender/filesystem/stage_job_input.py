from asyncio import create_subprocess_exec
from pathlib import Path
from typing import Optional

from aiofiles import open
from aiofiles.os import remove
from fastapi import UploadFile

CHUNK_SIZE = 1024 * 1024  # 1Mb


class UnsupportedContentTypeError(Exception):
    """When content type is unsupported."""


async def stage_job_input(
    job_dir: Path,
    archive: UploadFile,
    dest_fn: str = "archive.zip",
) -> None:
    """Copy archive file to job id directory.

    Args:
        job_dir: Where to put archive file.
        archive: The archive file with async read method.
        dest_fn: Filename of destination.

    Raises:
        ValueError: When unpacking archive failed.
    """
    _is_valid_content_type(archive.content_type)

    # Copy archive to disk
    job_archive = job_dir / dest_fn
    async with open(job_archive, "wb") as out_file:
        while content := await archive.read(CHUNK_SIZE):
            if isinstance(content, str):
                break  # type narrowing for mypy, content is always bytes
            await out_file.write(content)

    if archive.content_type in {"application/zip", "application/x-zip-compressed"}:
        # Use async subprocess to unpack file outside main thread
        # requires unzip command to be available on machine
        proc = await create_subprocess_exec("unzip", "-nqq", dest_fn, cwd=job_dir)
        returncode = await proc.wait()
        if returncode != 0:
            raise ValueError("Unpacking archive failed")

    await remove(job_archive)  # no longer needed?


def _is_valid_content_type(content_type: Optional[str]) -> bool:
    supported_upload_content_types = {
        "application/zip",
        "application/x-zip-compressed",
    }  # TODO add support for other formats like tar.gz, tar.bz2, .7z?
    if content_type not in supported_upload_content_types:
        raise UnsupportedContentTypeError(
            f"Unable to stage job input wrong mime type {content_type}, "
            + f"supported are {supported_upload_content_types}",
        )
    return True
