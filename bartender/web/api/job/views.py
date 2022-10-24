from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import Job
from bartender.db.models.user import User
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
) -> Optional[Job]:
    """
    Retrieve specific job from the database.

    :param jobid: name of job instance.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :raises HTTPException: When job is not found or user is not allowed to see job.
    :return: job models.
    """
    job = await job_dao.get_job(jobid=jobid)
    # TODO now get job that user submitted,
    # later also list jobs which are visible by admin
    # or are shared with current user
    if job is not None and job.submitter_id == user.id:
        # When job has state==ok then redirect to result page
        # When job has state==error then redirect to error page
        return job
    raise HTTPException(status_code=404, detail="Job not found")  # noqa: WPS432
