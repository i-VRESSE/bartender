from pathlib import Path
from shutil import rmtree
from typing import Annotated, Optional, Set, Tuple

from aiofiles.os import unlink
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import FileResponse, PlainTextResponse
from jsonschema import ValidationError
from pydantic import PositiveInt
from sqlalchemy.exc import NoResultFound
from starlette import status

from bartender.async_utils import async_wrap
from bartender.check_load import check_load
from bartender.config import CurrentConfig, InteractiveApplicationConfiguration
from bartender.context import CurrentContext, get_job_root_dir
from bartender.db.dao.job_dao import CurrentJobDAO
from bartender.db.models.job_model import MAX_LENGTH_NAME, CompletedStates, Job, State
from bartender.destinations import Destination
from bartender.filesystems.queue import CurrentFileOutStagingQueue
from bartender.schedulers.abstract import JobDescription
from bartender.walk_dir import DirectoryItem, walk_dir
from bartender.web.api.job.archive import ArchiveFormat, create_archive
from bartender.web.api.job.interactive_apps import InteractiveAppResult, run
from bartender.web.api.job.schema import JobModelDTO
from bartender.web.api.job.sync import sync_state, sync_states
from bartender.web.users import CurrentUser

router = APIRouter()


@router.get("/", response_model=list[JobModelDTO])
async def retrieve_jobs(  # noqa: WPS211
    job_dao: CurrentJobDAO,
    user: CurrentUser,
    context: CurrentContext,
    file_staging_queue: CurrentFileOutStagingQueue,
    limit: int = 10,
    offset: int = 0,
) -> list[Job]:
    """Retrieve all jobs of user from the database.

    Args:
        limit: limit of jobs.
        offset: offset of jobs.
        job_dao: JobDAO object.
        user: Current active user.
        context: Context with destinations.
        file_staging_queue: When scheduler reports job is complete.
            The output files need to be copied back.
            Use queue to perform download outside request/response handling.

    Returns:
        stream of jobs.
    """
    # TODO now list jobs that user submitted,
    # later also list jobs which are visible by admin
    # or are shared with current user
    jobs = await job_dao.get_all_jobs(limit=limit, offset=offset, user=user.username)
    # get current state for each job from scheduler
    await sync_states(
        jobs,
        context.destinations,
        job_dao,
        file_staging_queue,
    )
    return jobs


@router.get("/{jobid}", response_model=JobModelDTO)
async def retrieve_job(
    jobid: int,
    job_dao: CurrentJobDAO,
    user: CurrentUser,
    context: CurrentContext,
    file_staging_queue: CurrentFileOutStagingQueue,
) -> Job:
    """Retrieve specific job from the database.

    Args:
        jobid: identifier of job instance.
        job_dao: JobDAO object.
        user: Current active user.
        context: Context with destinations.
        file_staging_queue: When scheduler reports job is complete.
            The output files need to be copied back.
            Use queue to perform download outside request/response handling.

    Raises:
        HTTPException: When job is not found or user is not allowed to see job.

    Returns:
        job models.
    """
    try:
        # TODO now gets job that user submitted,
        # later also list jobs which are visible by admin
        # or are shared with current user
        # TODO When job has state==ok then include URL to applications result page
        # TODO When job has state==error then include URL to error page
        job = await job_dao.get_job(jobid=jobid, user=user.username)
        if job.destination is not None:
            destination = context.destinations[job.destination]
            await sync_state(
                job,
                job_dao,
                destination,
                file_staging_queue,
            )
        return job
    except NoResultFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


def get_job_dir(
    jobid: int,
    job_root_dir: Annotated[Path, Depends(get_job_root_dir)],
) -> Path:
    """Get directory where input and output files of a job reside.

    Args:
        jobid: The job identifier.
        job_root_dir: Directory in which all jobs are stored.

    Returns:
        Directory of job.
    """
    job_dir = job_root_dir / str(jobid)
    # TODO check it exist and is directory
    # unable to use pydantic.types.DirectoryPath as raises:
    # AttributeError: type object 'DirectoryPath' has no attribute '_flavour'
    return Path(job_dir)


def get_dir_of_completed_job(
    job: Annotated[Job, Depends(retrieve_job)],
    job_dir: Annotated[Path, Depends(get_job_dir)],
) -> Path:
    """Get directory of a completed job.

    Args:
        job: A job in any state.
        job_dir: Directory of job.

    Raises:
        HTTPException: When job is not completed.

    Returns:
        Directory of a completed job.
    """
    if job.state not in CompletedStates:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Job has not completed",
        )
    return job_dir


CurrentCompletedJobDir = Annotated[Path, Depends(get_dir_of_completed_job)]


@router.get(
    "/{jobid}/files/{path:path}",
    responses={
        200: {
            "content": {
                "application/octet-stream": {},
            },
        },
    },
    response_class=FileResponse,
)
def retrieve_job_file(
    path: str,
    job_dir: CurrentCompletedJobDir,
) -> FileResponse:
    """Retrieve file from a completed job.

    Args:
        path: Path to file that job has produced.
        job_dir: Directory with job output files.

    Raises:
        HTTPException: When file is not found or is not a file
            or is outside job directory.

    Returns:
        The file contents.
    """
    try:
        full_path = _resolve_path(path, job_dir)
        if not full_path.is_file():
            raise FileNotFoundError()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc
    return FileResponse(
        full_path,
        filename=path,
        # Allow browser to render file,
        # instead of always presenting save as dialog.
        content_disposition_type="inline",
    )


CurrentJob = Annotated[Job, Depends(retrieve_job)]


def get_destination(
    job: CurrentJob,
    context: CurrentContext,
) -> Destination:
    """Get the destination of a job.

    Args:
        job: The job.
        context: Context with destinations.

    Raises:
        ValueError: When job has no destination.

    Returns:
        The destination of the job.
    """
    if not job.destination or not job.internal_id:
        raise ValueError("Job has no destination")
    return context.destinations[job.destination]


CurrentDestination = Annotated[Destination, Depends(get_destination)]


async def get_completed_logs(
    job_dir: CurrentCompletedJobDir,
    job: CurrentJob,
    destination: CurrentDestination,
) -> Tuple[str, str]:
    """Get the standard output and error of a completed job.

    Args:
        job_dir: Directory with job output files.
        job: The job.
        destination: The destination of the job.

    Raises:
        ValueError: When job has no destination.
        HTTPException: When a log file is not found.

    Returns:
        The standard output and error.
    """
    try:
        if not job.internal_id:
            raise ValueError("Job has no internal_id")
        return await destination.scheduler.logs(job.internal_id, job_dir)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc


CurrentLogs = Annotated[Tuple[str, str], Depends(get_completed_logs)]


@router.get("/{jobid}/stdout", response_class=PlainTextResponse)
async def retrieve_job_stdout(
    logs: CurrentLogs,
) -> str:
    """Retrieve the jobs standard output.

    Args:
        logs: The standard output and error of a completed job.

    Returns:
        Content of standard output.
    """
    return logs[0]


@router.get("/{jobid}/stderr", response_class=PlainTextResponse)
def retrieve_job_stderr(
    logs: CurrentLogs,
) -> str:
    """Retrieve the jobs standard error.

    Args:
        logs: The standard output and error of a completed job.

    Returns:
        Content of standard error.
    """
    return logs[1]


@router.get(
    "/{jobid}/directories",
    response_model_exclude_none=True,
)
async def retrieve_job_directories(
    job_dir: CurrentCompletedJobDir,
    max_depth: PositiveInt = 1,
) -> DirectoryItem:
    """List directory contents of a job.

    Args:
        max_depth: Number of directories to traverse into.
        job_dir: The job directory.

    Returns:
        DirectoryItem: Listing of files and directories.
    """
    return await walk_dir(job_dir, job_dir, max_depth)


@router.get(
    "/{jobid}/directories/{path:path}",
    response_model_exclude_none=True,
)
async def retrieve_job_directories_from_path(
    path: str,
    job_dir: CurrentCompletedJobDir,
    max_depth: PositiveInt = 1,
) -> DirectoryItem:
    """List directory contents of a job.

    Args:
        path: Sub directory inside job directory to start from.
        max_depth: Number of directories to traverse into.
        job_dir: The job directory.

    Returns:
        DirectoryItem: Listing of files and directories.
    """
    subdirectory = _parse_subdirectory(path, job_dir)
    current_depth = len(subdirectory.relative_to(job_dir).parts)
    return await walk_dir(subdirectory, job_dir, current_depth + max_depth)


def _remove_archive(filename: str) -> None:
    """Remove archive after file response.

    Args:
        filename: path to the file that should be removed.
    """
    Path(filename).unlink()


@router.get(
    "/{jobid}/archive",
    responses={
        200: {
            "content": {
                "application/octet-stream": {},
            },
        },
    },
    response_class=FileResponse,
)
async def retrieve_job_directory_as_archive(  # noqa: WPS211
    job_dir: CurrentCompletedJobDir,
    background_tasks: BackgroundTasks,
    archive_format: ArchiveFormat = ".zip",
    exclude: Optional[list[str]] = Query(default=None),
    exclude_dirs: Optional[list[str]] = Query(default=None),
    filename: Optional[str] = Query(default=None),
    # Note: also tried to with include (filter & filter_dirs) but that can be
    # unintuitive. e.g. include_dirs=['output'] doesn't return subdirs of
    # /output that are not also called output. Might improve when globs will be
    # supported in next release (already documented):
    # https://github.com/PyFilesystem/pyfilesystem2/pull/464
) -> FileResponse:
    """Download contents of job directory as archive.

    Args:
        job_dir: The job directory.
        background_tasks: FastAPI mechanism for post-processing tasks
        archive_format: Format to use for archive. Supported formats are '.zip', '.tar',
            '.tar.xz', '.tar.gz', '.tar.bz2'
        exclude: list of filename patterns that should be excluded from archive.
        exclude_dirs: list of directory patterns that should be excluded from archive.
        filename: Name of the archive file to be returned.
            If not provided, uses id of the job.

    Returns:
        FileResponse: Archive containing the content of job_dir

    """
    archive_fn = str(job_dir.with_suffix(archive_format))
    await create_archive(job_dir, exclude, exclude_dirs, archive_format, archive_fn)

    background_tasks.add_task(_remove_archive, archive_fn)

    return_fn = Path(archive_fn).name
    if filename:
        return_fn = filename
    return FileResponse(archive_fn, filename=return_fn)


@router.get("/{jobid}/archive/{path:path}")
async def retrieve_job_subdirectory_as_archive(  # noqa: WPS211
    path: str,
    job_dir: CurrentCompletedJobDir,
    background_tasks: BackgroundTasks,
    archive_format: ArchiveFormat = ".zip",
    exclude: Optional[list[str]] = Query(default=None),
    exclude_dirs: Optional[list[str]] = Query(default=None),
    filename: Optional[str] = Query(default=None),
) -> FileResponse:
    """Download job output as archive.

    Args:
        path: Sub directory inside job directory to start from.
        job_dir: The job directory.
        background_tasks: FastAPI mechanism for post-processing tasks
        archive_format: Format to use for archive. Supported formats are '.zip',
            '.tar', '.tar.xz', '.tar.gz', '.tar.bz2'
        exclude: list of filename patterns that should be excluded from archive.
        exclude_dirs: list of directory patterns that should be excluded from archive.
        filename: Name of the archive file to be returned.
            If not provided, uses id of the job.

    Returns:
        FileResponse: Archive containing the output of job_dir

    """
    subdirectory = _parse_subdirectory(path, job_dir)
    return await retrieve_job_directory_as_archive(
        subdirectory,
        background_tasks,
        archive_format=archive_format,
        exclude=exclude,
        exclude_dirs=exclude_dirs,
        filename=filename,
    )


def _resolve_path(path: str, job_dir: Path) -> Path:
    resolved_job_dir = job_dir.resolve(strict=True)
    resolved = (resolved_job_dir / path).resolve(strict=True)
    if not resolved.is_relative_to(resolved_job_dir):
        raise FileNotFoundError()
    return resolved


def _parse_subdirectory(path: str, job_dir: Path) -> Path:
    try:
        subdirectory = _resolve_path(path, job_dir)
        if not subdirectory.is_dir():
            raise FileNotFoundError()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc

    return job_dir / path


def get_interactive_app(
    application: str,
    config: CurrentConfig,
) -> InteractiveApplicationConfiguration:
    """Get interactive app configuration.

    Args:
        application: The interactive application.
        config: The bartender configuration.

    Returns:
        The interactive application configuration.

    """
    return config.interactive_applications[application]


CurrentInteractiveAppConf = Annotated[
    InteractiveApplicationConfiguration,
    Depends(get_interactive_app),
]


@router.post(
    "/{jobid}/interactive/{application}",
)
async def run_interactive_app(
    request: Request,
    job_dir: CurrentCompletedJobDir,
    job: CurrentJob,
    application: CurrentInteractiveAppConf,
) -> InteractiveAppResult:
    """Run interactive app on a completed job.

    Args:
        request: The request.
        job_dir: The job directory.
        job: The job.
        application: The interactive application.

    Returns:
        The result of running the interactive application.

    Raises:
        HTTPException: When job was not run with
            the required application or the payload is invalid
            or the load on the machine is too high.
    """
    check_load()
    if application.job_application and application.job_application != job.application:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f'Job was not run with application "{job.application}"',
        )
    payload = await request.json()
    try:
        return await run(job_dir, payload, application)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.message,
        ) from exc


@router.post("/{jobid}/name")
async def rename_job_name(
    jobid: int,
    job_dao: CurrentJobDAO,
    user: CurrentUser,
    name: Annotated[str, Body(max_length=MAX_LENGTH_NAME, min_length=1)],
) -> None:
    """Rename the name of a job.

    Args:
        jobid: The job identifier.
        job_dao: The job DAO.
        user: The current user.
        name: The new name of the job.

    Raises:
        HTTPException: When job is not found. Or when user is not owner of job.
    """
    try:
        await job_dao.set_job_name(jobid, user.username, name)
    except IndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


@router.delete("/{jobid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(  # noqa: WPS211
    jobid: int,
    job_dao: CurrentJobDAO,
    job: Annotated[Job, Depends(retrieve_job)],
    user: CurrentUser,
    job_dir: Annotated[Path, Depends(get_job_dir)],
    destination: CurrentDestination,
    job_root_dir: Annotated[Path, Depends(get_job_root_dir)],
) -> None:
    """Delete a job.

    Deletes job from database and filesystem.

    When job is queued or running it will be canceled
    and removed from the filesystem where the job is located.

    Args:
        jobid: The job identifier.
        job_dao: The job DAO.
        job: The job.
        user: The current user.
        job_dir: The job directory.
        destination: The destination of the job.
        job_root_dir: The root directory of all jobs.

    Raises:
        HTTPException: When job is not found.
            Or when user is not owner of job.
            Or when job is in state that cannot be deleted.

    """
    cancelable_states: Set[State] = {"queued", "running"}
    if job.state in cancelable_states and job.internal_id is not None:
        await destination.scheduler.cancel(job.internal_id)
        description = JobDescription(job_dir=job_dir, command="echo")
        localized_description = destination.filesystem.localize_description(
            description,
            job_root_dir,
        )
        await destination.filesystem.delete(localized_description)

    undeletable_states: Set[State] = {"new", "staging_out"}
    if job.state in undeletable_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be deleted in its current state",
        )

    if job_dir.is_symlink():
        # We want to remove the symlink not its target
        await unlink(job_dir)
    else:
        await async_wrap(rmtree)(job_dir)

    await job_dao.delete_job(jobid, user.username)
