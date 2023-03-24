from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import PositiveInt
from sqlalchemy.exc import NoResultFound
from starlette import status

from bartender.context import CurrentContext, get_job_root_dir
from bartender.db.dao.job_dao import CurrentJobDAO
from bartender.db.models.job_model import CompletedStates, Job
from bartender.filesystem.walk_dir import DirectoryItem, walk_dir
from bartender.filesystems.queue import CurrentFileOutStagingQueue
from bartender.web.api.job.schema import JobModelDTO
from bartender.web.api.job.sync import sync_state, sync_states
from bartender.web.users.manager import CurrentUser

router = APIRouter()


@router.get("/", response_model=List[JobModelDTO])
async def retrieve_jobs(  # noqa: WPS211
    job_dao: CurrentJobDAO,
    user: CurrentUser,
    context: CurrentContext,
    file_staging_queue: CurrentFileOutStagingQueue,
    limit: int = 10,
    offset: int = 0,
) -> List[Job]:
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
    jobs = await job_dao.get_all_jobs(limit=limit, offset=offset, user=user)
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
        job = await job_dao.get_job(jobid=jobid, user=user)
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


@router.get("/{jobid}/stdout")
def retrieve_job_stdout(
    job_dir: CurrentCompletedJobDir,
) -> FileResponse:
    """Retrieve the jobs standard output.

    Args:
        job_dir: Directory with job output files.

    Returns:
        Content of standard output.
    """
    return retrieve_job_files("stdout.txt", job_dir)


@router.get("/{jobid}/stderr")
def retrieve_job_stderr(
    job_dir: CurrentCompletedJobDir,
) -> FileResponse:
    """Retrieve the jobs standard error.

    Args:
        job_dir: Directory with job output files.

    Returns:
        Content of standard error.
    """
    return retrieve_job_files("stderr.txt", job_dir)


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

    Raises:
        HTTPException: When path is not found or is outside job directory.

    Returns:
        DirectoryItem: Listing of files and directories.
    """
    try:
        start_dir = (job_dir / path).expanduser().resolve(strict=True)
        if not start_dir.is_relative_to(job_dir):
            raise FileNotFoundError()
        if not start_dir.is_dir():
            raise FileNotFoundError()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        ) from exc
    current_depth = len(start_dir.relative_to(job_dir).parts)
    return await walk_dir(start_dir, job_dir, current_depth + max_depth)
