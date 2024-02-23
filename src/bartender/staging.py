from pathlib import Path
from shutil import unpack_archive
from typing import Literal, Optional

from aiofiles import open
from aiofiles.os import mkdir, remove
from fastapi import HTTPException, UploadFile
from starlette import status

from bartender.async_utils import async_wrap
from bartender.config import ApplicatonConfiguration

CHUNK_SIZE = 1024 * 1024  # 1Mb


class UnsupportedContentTypeError(Exception):
    """When content type is unsupported."""


def has_needed_files(
    application: ApplicatonConfiguration,
    job_dir: Path,
) -> Literal[True]:
    """Check if files required by application are present in job directory.

    Args:
        application: Name of application to check config file for.
        job_dir: In which directory to look.

    Raises:
        IndexError: When one or more needed files can not be found

    Returns:
        True when found or no files where needed.
    """
    missing_files = []
    for needed_file in application.upload_needs:
        file = job_dir / needed_file
        file_exists = file.exists() and file.is_file()
        if not file_exists:
            missing_files.append(needed_file)
    if missing_files:
        raise IndexError(
            f"Application requires files {missing_files}, "
            "but where not found in uploaded zip archive",
        )
    return True


async def create_job_dir(job_id: int, job_root_dir: Path) -> Path:
    """Create job directory.

    Args:
        job_id: id of the job.
        job_root_dir: Root directory for all jobs.

    Raises:
        HTTPException: When job directory could not be made.

    Returns:
        Directory of job.
    """
    job_dir: Path = job_root_dir / str(job_id)

    try:
        await mkdir(job_dir)
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create directory for job.",
        ) from exc
    return job_dir


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


async def unpack_upload(
    job_dir: Path,
    archive: UploadFile,
    dest_fn: str = "archive.zip",
) -> None:
    """Unpack archive file to job id directory.

    Args:
        job_dir: Where to put archive file.
        archive: The archive file with async read method.
        dest_fn: Temporary archive filename.
    """
    _is_valid_content_type(archive.content_type)

    # Copy archive to disk
    job_archive = job_dir / dest_fn
    # If archive contains
    async with open(job_archive, "wb") as out_file:
        while content := await archive.read(CHUNK_SIZE):
            if isinstance(content, str):
                break  # type narrowing for mypy, content is always bytes
            await out_file.write(content)

    if archive.content_type in {"application/zip", "application/x-zip-compressed"}:
        await async_wrap(unpack_archive)(job_archive, extract_dir=job_dir, format="zip")
    # TODO what happens when archive contains archive.zip, will it overwrite itself?

    await remove(job_archive)  # no longer needed?
