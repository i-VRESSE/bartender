from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from starlette import status
from starlette.background import BackgroundTask

from bartender.config import Config, get_config
from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.user import User
from bartender.filesystem import has_config_file
from bartender.filesystem.assemble_job import assemble_job
from bartender.filesystem.stage_job_input import stage_job_input
from bartender.web.api.applications.submit import submit
from bartender.web.users.manager import current_active_user, current_api_token

router = APIRouter()


@router.get("/", response_model=list[str])
def list_applications(config: Config = Depends(get_config)) -> list[str]:
    """List application names.

    :param config: Config with applications.
    :return: The list.
    """
    # TODO also return values or at least the expected config file name for each app
    return list(config.applications.keys())


@router.put(
    "/{application}/job",
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
async def upload_job(  # noqa: WPS211
    application: str,
    request: Request,
    upload: UploadFile = File(description="Archive with config file for application"),
    job_dao: JobDAO = Depends(),
    submitter: User = Depends(current_active_user),
    config: Config = Depends(get_config),
) -> RedirectResponse:
    """
    Creates job model in the database, stage archive locally and submit to scheduler.

    :param application: Name of application to run job for.
    :param upload: Archive with config file for application.
    :param request: request object.
    :param job_dao: JobDAO object.
    :param submitter: User who submitted job.
    :param config: Configuration with applications and destinations.
    :raises IndexError: When job could not created inside database or
        when config file was not found.
    :raises KeyError: Application is invalid.
    :return: redirect response.
    """
    if application not in config.applications:
        valid = config.applications.keys()
        raise KeyError(f"Invalid application. Valid applications: {valid}")
    job_id = await job_dao.create_job(upload.filename, application, submitter)
    if job_id is None:
        raise IndexError("Failed to create database entry for job")

    job_dir = assemble_job(
        job_id,
        await current_api_token(submitter),
        config.job_root_dir,
    )
    await stage_job_input(job_dir, upload)
    has_config_file(config.applications[application], job_dir)

    task = BackgroundTask(
        submit,
        job_id,
        job_dir,
        application,
        job_dao,
        config,
    )

    url = request.url_for("retrieve_job", jobid=job_id)
    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
        background=task,
    )
