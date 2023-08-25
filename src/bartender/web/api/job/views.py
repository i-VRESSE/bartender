from pathlib import Path
from typing import Annotated, Literal, Optional, Tuple, Type, Union

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, PlainTextResponse
from fs.copy import copy_fs
from fs.osfs import OSFS
from fs.tarfs import TarFS
from fs.walk import Walker
from fs.zipfs import ZipFS
from pydantic import PositiveInt
from sqlalchemy.exc import NoResultFound
from starlette import status

from bartender.async_utils import async_wrap
from bartender.context import CurrentContext, get_job_root_dir
from bartender.db.dao.job_dao import CurrentJobDAO
from bartender.db.models.job_model import CompletedStates, Job
from bartender.filesystem.walk_dir import DirectoryItem, walk_dir
from bartender.filesystems.queue import CurrentFileOutStagingQueue
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


@router.get("/{jobid}/files/{path:path}")
def retrieve_job_files(
    path: str,
    job_dir: CurrentCompletedJobDir,
) -> FileResponse:
    """Retrieve files from a completed job.

    Args:
        path: Path to file that job has produced.
        job_dir: Directory with job output files.

    Raises:
        HTTPException: When file is not found or is outside job directory.

    Returns:
        The file content.
    """
    try:
        full_path = (job_dir / path).expanduser().resolve(strict=True)
        if not full_path.is_relative_to(job_dir):
            raise FileNotFoundError()
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


@router.post("/{jobid}/files/{path:path}", status_code=status.HTTP_201_CREATED)
async def add_job_file(
    path: str,
    job_dir: CurrentCompletedJobDir,
    file: UploadFile = File(description="File to add to job."),
):
    """Upload file to completed job.

    Can only create new file, existing files cannot be overwritten.

    After job is completed you can do additional analysis on the output files.
    This endpoint allows you to upload the analysis results to the job directory.

    Args:
        path: Name of file you want to retrieve uploaded file as.
        file: File to upload.
        job_dir: Directory with job files.

    Raises:
        HTTPException: When file already exists or is outside job directory.

    Returns:
        Created 201
    """
    try:
        full_path = (job_dir / path).expanduser().resolve(strict=True)
        if not full_path.is_relative_to(job_dir):
            raise FileNotFoundError()
        if not full_path.exists():
            raise FileExistsError()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="File or directory already exists",
        ) from exc
    async with open(full_path, "wb") as out_file:
        CHUNK_SIZE = 1024 * 1024  # 1Mb
        while content := await file.read(CHUNK_SIZE):
            if isinstance(content, str):
                break  # type narrowing for mypy, content is always bytes
            await out_file.write(content)


CurrentJob = Annotated[Job, Depends(retrieve_job)]


async def get_completed_logs(
    job_dir: CurrentCompletedJobDir,
    job: CurrentJob,
    context: CurrentContext,
) -> Tuple[str, str]:
    """Get the standard output and error of a completed job.

    Args:
        job_dir: Directory with job output files.
        job: The job.
        context: Context with destinations.

    Raises:
        ValueError: When job has no destination.

    Returns:
        The standard output and error.
    """
    if not job.destination or not job.internal_id:
        raise ValueError("Job has no destination")
    destination = context.destinations[job.destination]
    return await destination.scheduler.logs(job.internal_id, job_dir)


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


ArchiveFormats = Literal[".zip", ".tar", ".tar.xz", ".tar.gz", ".tar.bz2"]


@router.get(
    "/{jobid}/archive",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def retrieve_job_directory_as_archive(
    job_dir: CurrentCompletedJobDir,
    background_tasks: BackgroundTasks,
    archive_format: ArchiveFormats = ".zip",
    exclude: Optional[list[str]] = Query(default=None),
    exclude_dirs: Optional[list[str]] = Query(default=None),
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

    Returns:
        FileResponse: Archive containing the content of job_dir

    """
    dst_fs = _parse_archive_format(archive_format)
    archive_fn = str(job_dir.with_suffix(archive_format))
    with (  # noqa: WPS316
        OSFS(str(job_dir)) as src,
        dst_fs(archive_fn, write=True) as dst,
    ):
        await async_wrap(copy_fs)(
            src,
            dst,
            walker=Walker(exclude=exclude, exclude_dirs=exclude_dirs),
        )

    background_tasks.add_task(_remove_archive, archive_fn)

    return_fn = Path(archive_fn).name
    return FileResponse(archive_fn, filename=return_fn)


def _parse_archive_format(
    archive_format: ArchiveFormats,
) -> Union[Type[ZipFS], Type[TarFS]]:
    if archive_format == ".zip":
        return ZipFS
    return TarFS


@router.get("/{jobid}/archive/{path:path}")
async def retrieve_job_subdirectory_as_archive(  # noqa: WPS211
    path: str,
    job_dir: CurrentCompletedJobDir,
    background_tasks: BackgroundTasks,
    archive_format: ArchiveFormats = ".zip",
    exclude: Optional[list[str]] = Query(default=None),
    exclude_dirs: Optional[list[str]] = Query(default=None),
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
    )


def _parse_subdirectory(path: str, job_dir: Path) -> Path:
    try:
        subdirectory = (job_dir / path).expanduser().resolve(strict=True)
        if not subdirectory.is_relative_to(job_dir):
            raise FileNotFoundError()
        if not subdirectory.is_dir():
            raise FileNotFoundError()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc

    return subdirectory
