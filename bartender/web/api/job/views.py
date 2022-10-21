from functools import partialmethod
from typing import Coroutine, List, Optional
from anyio import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from starlette import status
from starlette.background import BackgroundTask

from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import Job
from bartender.filesystem import has_config_file
from bartender.filesystem.assemble_job import assemble_job
from bartender.filesystem.stage_job_input import stage_job_input
from bartender.schedulers.direct import submit
from bartender.settings import settings
from bartender.web.api.job.schema import JobModelDTO, JobModelInputDTO
from bartender.web.users.manager import current_api_token

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


class JobCreationError(Exception):
    """When job could not be created."""


# Q: POST or PUT?
@router.put("/", status_code=status.HTTP_303_SEE_OTHER, response_class=RedirectResponse)
async def create_job(
    new_job_object: JobModelInputDTO,
    request: Request,
    job_dao: JobDAO = Depends(JobDAO),
    token: str = Depends(current_api_token),
) -> RedirectResponse:
    """
    Creates job model in the database.

    :param new_job_object: new job model.
    :param request: request object.
    :param job_dao: JobDAO object.
    :param token: Token that job can use to talk to bartender service.
    :raises JobCreationError: When job could not be created.
    :return: redirect response.
    """
    first_app_name = next(iter(settings.applications))
    jobid = await job_dao.create_job(
        application=first_app_name,
        **new_job_object.dict(),
    )
    if jobid is None:
        raise JobCreationError()

    # Setup goes here!
    assemble_job(jobid, token)

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


@router.put(
    "/upload/{application}",
    status_code=status.HTTP_303_SEE_OTHER,
    response_class=RedirectResponse,
    openapi_extra={
        # Enfore uploaded file is a certain content type
        # See https://github.com/OAI/OpenAPI-Specification/blob/main/versions/3.0.3.md#encoding-object  # noqa: E501
        # does not seem supported by Swagger UI or FastAPI
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "encoding": {"upload": {"contentType": "application/zip"}},
                },
            },
        },
    },
)
async def upload_job(
    application: str,
    request: Request,
    upload: UploadFile = File(
        description="Archive with config file for application",
        default=None,
    ),
    job_dao: JobDAO = Depends(),
    token: str = Depends(current_api_token),
) -> RedirectResponse:
    """
    Creates job model in the database and stage archive.

    :param application: Name of application to run job for.
    :param upload: Archive with config file for application.
    :param request: request object.
    :param job_dao: JobDAO object.
    :param token: Token that job can use to talk to bartender service.
    :raises IndexError: When job could not created inside database or
        when config file was not found.
    :raises KeyError: Application is invalid.
    :return: redirect response.
    """
    if application not in settings.applications:
        valid = settings.applications.keys()
        raise KeyError(f"Invalid application. Valid applications: {valid}")
    job_id = await job_dao.create_job(upload.filename, application)
    if job_id is None:
        raise IndexError("Failed to create database entry for job")

    job_dir = assemble_job(job_id, token)
    await stage_job_input(job_dir, upload)
    has_config_file(application, job_dir)

    url = request.url_for("retrieve_job", jobid=job_id)

    # TODO submit should be an adapter,
    # which can submit job to one of the available schedulers
    # based on job input, application, scheduler resources, phase of moon, etc.
    async def update_state(state: Job.states) -> Coroutine[Any, Any, None]:
        if job_id is None:
            raise IndexError("Failed to create database entry for job")
        await job_dao.update_job_state(job_id, state)

    task = BackgroundTask(
        submit,
        job_dir=job_dir,
        app=settings.applications[application],
        update_state=update_state,
    )

    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
        background=task,
    )
