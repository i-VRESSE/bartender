# This puts the files in the directories

from pathlib import Path

from fastapi import HTTPException
from starlette import status

from bartender.settings import settings


# TODO: Make this async
def assemble_job(job_id: int, job_token: str) -> Path:
    """
    Assembly the job.

    Create job directory and metadata file.
    Metadata file contains job id and token.

    :param job_id: id of the job.
    :param job_token: Token that can be used to talk to bartender service.
    :raises HTTPException: When job directory could not be made.
    :return: Directory of job.
    """
    job_dir: Path = settings.job_root_dir / str(job_id)

    try:
        job_dir.mkdir()
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create directory for job.",
        ) from exc

    meta_file = job_dir / "meta"
    body = f"{job_id}\n{job_token}\n"
    meta_file.write_text(body)
    return job_dir
