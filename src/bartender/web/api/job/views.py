from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound
from starlette import status

from bartender.context import Context, get_context, get_job_root_dir
from bartender.db.dao.job_dao import JobDAO
from bartender.db.models.job_model import Job
from bartender.db.models.user import User
from bartender.web.api.job.schema import JobModelDTO
from bartender.web.api.job.sync import sync_state, sync_states
from bartender.web.users.manager import current_active_user

router = APIRouter()


@router.get("/", response_model=List[JobModelDTO])
async def retrieve_jobs(
    limit: int = 10,
    offset: int = 0,
    job_dao: JobDAO = Depends(),
    user: User = Depends(current_active_user),
    context: Context = Depends(get_context),
) -> List[Job]:
    """Retrieve all jobs of user from the database.

    Args:
        limit: limit of jobs.
        offset: offset of jobs.
        job_dao: JobDAO object.
        user: Current active user.
        context: Context with destinations.

    Returns:
        stream of jobs.
    """
    # TODO now list jobs that user submitted,
    # later also list jobs which are visible by admin
    # or are shared with current user
    jobs = await job_dao.get_all_jobs(limit=limit, offset=offset, user=user)
    # get current state for each job from scheduler
    await sync_states(jobs, context.destinations, job_dao, context.job_root_dir)
    return jobs


@router.get("/{jobid}", response_model=JobModelDTO)
async def retrieve_job(
    jobid: int,
    job_dao: JobDAO = Depends(),
    user: User = Depends(current_active_user),
    context: Context = Depends(get_context),
) -> Job:
    """Retrieve specific job from the database.

    Args:
        jobid: identifier of job instance.
        job_dao: JobDAO object.
        user: Current active user.
        context: Context with destinations.

    Raises:
        HTTPException: When job is not found or user is not allowed to see job.

    Returns:
        job models.
    """
    try:
        # TODO now get job that user submitted,
        # later also list jobs which are visible by admin
        # or are shared with current user
        # TODO When job has state==ok then include URL to applications result page
        # TODO When job has state==error then include URL to error page
        job = await job_dao.get_job(jobid=jobid, user=user)
        if job.destination is not None:
            destination = context.destinations[job.destination]
            await sync_state(job, job_dao, destination, context.job_root_dir)
        return job
    except NoResultFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


def get_job_dir(jobid: int, job_root_dir: Path = Depends(get_job_root_dir)) -> Path:
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
    job: Job = Depends(retrieve_job),
    job_dir: Path = Depends(get_job_dir),
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
    if job.state not in {"ok", "error"}:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail="Job has not completed",
        )
    return job_dir


@router.get("/{jobid}/files/{path:path}", response_class=FileResponse)
def retrieve_job_files(
    path: str,
    job_dir: Path = Depends(get_dir_of_completed_job),
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


@router.get("/{jobid}/stdout", response_class=FileResponse)
def retrieve_job_stdout(
    job_dir: Path = Depends(get_dir_of_completed_job),
) -> FileResponse:
    """Retrieve the jobs standard output.

    Args:
        job_dir: Directory with job output files.

    Returns:
        Content of standard output.
    """
    return retrieve_job_files("stdout.txt", job_dir)


@router.get("/{jobid}/stderr", response_class=FileResponse)
def retrieve_job_stderr(
    job_dir: Path = Depends(get_dir_of_completed_job),
) -> FileResponse:
    """Retrieve the jobs standard error.

    Args:
        job_dir: Directory with job output files.

    Returns:
        Content of standard error.
    """
    return retrieve_job_files("stderr.txt", job_dir)


class DirectoryItem(BaseModel):
    """A entry in a directory."""

    name: str
    path: Path
    is_dir: bool
    is_file: bool
    children: Optional[list["DirectoryItem"]]


@router.get(
    "/{jobid}/directories",
    response_model=DirectoryItem,
    response_model_exclude_none=True,
)
def retrieve_job_directories(
    depth: int = 1,
    job_dir: Path = Depends(get_dir_of_completed_job),
) -> DirectoryItem:
    """List directory contents of a job.

    Args:
        depth: Number of directories to traverse into.
        job_dir: The job directory.

    Returns:
        DirectoryItem: Listing of files and directories.
    """
    return walk_job_dir(job_dir, job_dir, depth)


def walk_job_dir(path: Path, root: Path, max_depth: int) -> DirectoryItem:
    """Traverse job dir returning the file names and directory names inside.

    Args:
        path: Path relative to root.
        root: The starting path.
        max_depth: Number of directories to traverse into.

    Returns:
        a tree of directory items.
    """
    # TODO make async using aiofiles
    is_dir = path.is_dir()
    rpath = path.relative_to(root)
    item = DirectoryItem(
        name=rpath.name,
        path=rpath,
        is_dir=is_dir,
        is_file=path.is_file(),
    )
    if is_dir:
        current_depth = len(rpath.parts)
        if current_depth < max_depth:
            item.children = [
                walk_job_dir(sub_path, root, max_depth) for sub_path in path.iterdir()
            ]
    return item
