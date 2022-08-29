from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from starlette import status

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import Job
from bartender.filesystem.assemble_job import assemble_job
from bartender.web.api.job.schema import JobModelDTO, JobModelInputDTO

router = APIRouter()


@router.get("/", response_model=List[JobModelDTO])
async def retrieve_jobs(
    limit: int = 10,
    offset: int = 0,
    job_dao: JobDAO = Depends(),
) -> List[Job]:
    """
    Retrieve all jobs from the database.

    :param limit: limit of jobs.
    :param offset: offset of jobs.
    :param job_dao: JobDAO object.
    :return: stream of jobs.
    """
    return await job_dao.get_all_jobs(limit=limit, offset=offset)


# Q: POST or PUT?
@router.put("/", status_code=status.HTTP_303_SEE_OTHER, response_class=RedirectResponse)
async def create_job(
    new_job_object: JobModelInputDTO,
    request: Request,
    job_dao: JobDAO = Depends(),
) -> RedirectResponse:
    """
    Creates job model in the database.

    :param new_job_object: new job model.
    :param request: request object.
    :param job_dao: JobDAO object.
    :return: redirect response.
    """
    jobid = await job_dao.create_job(**new_job_object.dict())

    # Setup goes here!
    if jobid:
        assemble_job(jobid)

    url = request.url_for("retrieve_job", jobid=jobid)

    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{jobid}", response_model=JobModelDTO)
async def retrieve_job(
    jobid: int,
    job_dao: JobDAO = Depends(),
) -> Optional[Job]:
    """
    Retrieve specific job from the database.

    :param jobid: name of job instance.
    :param job_dao: JobDAO object.
    :return: job models.
    """
    return await job_dao.get_job(jobid=jobid)
