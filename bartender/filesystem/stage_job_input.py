from pathlib import Path

import aiofiles
from fastapi import UploadFile

CHUNK_SIZE = 1024 * 1024  # 1Mb


async def stage_job_input(
    job_dir: Path,
    archive: UploadFile,
    dest_fn: str = "archive.zip",
) -> None:
    """
    Copy archive file to job id directory.

    :param job_dir: Where to put archive file.
    :param archive: The archive file with async read method.
    :param dest_fn: Filename of destination.

    :raises ValueError: When mime type is unsupported
    """
    suppoprted_upload_mimetypes = {
        "application/zip",
    }  # TODO add support for other formats like tar.gz, tar.bz2, .7z?
    if archive.content_type not in suppoprted_upload_mimetypes:
        raise ValueError(
            f"Unable to stage job input wrong mime type {archive.content_type}"
            + f"supported are {suppoprted_upload_mimetypes}",
        )

    job_archive = job_dir / dest_fn
    async with aiofiles.open(job_archive, "wb") as out_file:
        while content := await archive.read(CHUNK_SIZE):
            if isinstance(content, str):
                break  # type narrowing for mypy, content is always bytes
            await out_file.write(content)
            # TODO extract files from archive,
            # as it is CPU and IO intensive should be done outside main web thread
            # TODO check whether it contains the file needed by the application.
            # For example haddock3 application requires a TOML formatted config file.
