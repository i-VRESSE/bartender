from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.datastructures import FormData
from fastapi.responses import RedirectResponse
from jsonschema import Draft202012Validator
from starlette import status
from starlette.background import BackgroundTask

from bartender.config import ApplicatonConfiguration
from bartender.context import Context, CurrentContext
from bartender.db.dao.job_dao import CurrentJobDAO
from bartender.filesystem import has_needed_files
from bartender.filesystem.assemble_job import assemble_job
from bartender.filesystem.stage_job_input import stage_job_input
from bartender.web.api.applications.submit import submit
from bartender.web.users import CurrentUser, User

router = APIRouter()


@router.put(
    "/{application}",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
)
async def upload_job(  # noqa: WPS210, WPS211
    application: str,
    request: Request,
    job_dao: CurrentJobDAO,
    submitter: CurrentUser,
    context: CurrentContext,
    upload: UploadFile = File(description="Archive with files needed for application"),
) -> RedirectResponse:
    """Creates job model in the database, stage archive locally and submit to scheduler.

    Args:
        application: Name of application to run job for.
        upload: Archive with config file for application.
        request: request object.
        job_dao: JobDAO object.
        submitter: User who submitted job.
        context: Context with applications and destinations.

    Raises:
        IndexError: When job could not created inside database or when config
            file was not found.
        HTTPException: Application is invalid.

    Returns:
        redirect response to created job.
    """
    if application not in context.applications:
        valid = context.applications.keys()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid application. Valid applications: {valid}",
        )
    _check_role(application, submitter, context)
    job_id = await job_dao.create_job(upload.filename, application, submitter.username)
    if job_id is None:
        raise IndexError("Failed to create database entry for job")

    job_dir = assemble_job(
        job_id,
        submitter.apikey,
        context.job_root_dir,
    )
    # TODO uploaded file can be big, and thus take long time to unpack,
    # not nice to do it in request/response handling,
    # as request could timeout on consumer side.
    # Move to background task or have dedicated routes for preparing input files.
    await stage_job_input(job_dir, upload)
    has_needed_files(context.applications[application], job_dir)
    payload = await _validate_form(request, context.applications[application])

    task = BackgroundTask(
        submit,
        job_id,
        job_dir,
        application,
        submitter,
        payload,
        job_dao,
        context,
    )

    url = request.url_for("retrieve_job", jobid=job_id)
    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
        background=task,
    )


def _check_role(application: str, submitter: User, context: Context) -> None:
    """Check whether submitter is allowed to use application.

    When application has some allowed_roles defined then
    the submitter should have at least one of those roles to continue.

    When application has no allowed_roles defined then
    the submitter is allowed to continue.

    Args:
        application: Name of application to run job for.
        submitter: User who submitted job.
        context: Context with applications.

    Raises:
        HTTPException: When submitter is missing role.
    """
    allowed_roles = context.applications[application].allowed_roles
    if allowed_roles and not set(submitter.roles) & set(allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing role.",
        )


async def _validate_form(
    request: Request,
    config: ApplicatonConfiguration,
) -> dict[str, str]:
    """
    Validates the form request against the config.input_schema if it is defined.

    Args:
        request: The request object.
        config: The configuration for the application.

    Returns:
        The payload extracted from the form request.
        Without any files or duplicate keys.
    """
    if config.input_schema is None:
        return {}
    max_fields = len(config.input_schema.get("properties", {})) + 1
    async with request.form(max_files=1, max_fields=max_fields) as form:
        payload = _extract_payload_from_form(form)
        validator = Draft202012Validator(config.input_schema)
        # payload values are strings, while the input_schema might expect other types
        # TODO convert strings to numbers or booleans where needed.
        # use https://jschon.readthedocs.io evaluate().output()?
        # now throws an error if schema expects non-string
        validator.validate(payload)

    return payload


def _extract_payload_from_form(form: FormData) -> dict[str, str]:
    """Extracts the payload from the form request.

    Args:
        form: The form request.

    Returns:
        The payload extracted from the form request.
        Without any files or duplicate keys.
    """
    return {formk: formv for formk, formv in form.items() if isinstance(formv, str)}
