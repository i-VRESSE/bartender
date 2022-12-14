from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.exc import NoResultFound
from starlette import status

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import Job
from bartender.db.models.user import User
from bartender.settings import settings
from bartender.web.api.job.schema import JobModelDTO
from bartender.web.users.manager import current_active_user

router = APIRouter()


@router.get("/", response_model=List[JobModelDTO])
async def retrieve_jobs(
    limit: int = 10,
    offset: int = 0,
    job_dao: JobDAO = Depends(),
    user: User = Depends(current_active_user),
) -> List[Job]:
    """
    Retrieve all jobs of user from the database.

    :param limit: limit of jobs.
    :param offset: offset of jobs.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :return: stream of jobs.
    """
    # TODO now list jobs that user submitted,
    # later also list jobs which are visible by admin
    # or are shared with current user
    return await job_dao.get_all_jobs(limit=limit, offset=offset, user=user)


@router.get("/{jobid}", response_model=JobModelDTO)
async def retrieve_job(
    jobid: int,
    job_dao: JobDAO = Depends(),
    user: User = Depends(current_active_user),
) -> Job:
    """
    Retrieve specific job from the database.

    :param jobid: name of job instance.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :raises HTTPException: When job is not found or user is not allowed to see job.
    :return: job models.
    """
    try:
        # TODO now get job that user submitted,
        # later also list jobs which are visible by admin
        # or are shared with current user
        # TODO When job has state==ok then include URL to applications result page
        # TODO When job has state==error then include URL to error page
        return await job_dao.get_job(jobid=jobid, user=user)
    except NoResultFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


@router.get("/{jobid}/stdout", response_class=FileResponse)
async def retrieve_job_stdout(
    jobid: int,
    job_dao: JobDAO = Depends(),
    user: User = Depends(current_active_user),
) -> FileResponse:
    """Retrieve stdout of a job.

    :param jobid: name of job instance.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :raises HTTPException: When job is not found or user is not allowed to see job.
    :return: stdout of job.
    """
    job = await retrieve_job(jobid=jobid, job_dao=job_dao, user=user)
    if job.state not in {"ok", "error"}:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Stdout not ready. Job has not completed.",
        )
    stdout: Path = settings.job_root_dir / str(jobid) / "stdout.txt"
    return FileResponse(stdout)
