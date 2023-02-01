from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
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
    """
    Retrieve all jobs of user from the database.

    :param limit: limit of jobs.
    :param offset: offset of jobs.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :param context: Context with destinations.
    :return: stream of jobs.
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
    """
    Retrieve specific job from the database.

    :param jobid: identifier of job instance.
    :param job_dao: JobDAO object.
    :param user: Current active user.
    :param context: Context with destinations.
    :raises HTTPException: When job is not found or user is not allowed to see job.
    :return: job models.
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
            # TODO perform syncing of states in background task
            # sync can include downloading of big job dir from remote to local,
            await sync_state(job, job_dao, destination, context.job_root_dir)
        return job
    except NoResultFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        ) from exc


def get_job_dir(jobid: int, job_root_dir: Path = Depends(get_job_root_dir)) -> Path:
    """Get directory where input and output files of a job reside.

    :param jobid: The job identifier.
    :param job_root_dir: Directory in which all jobs are stored.
    :return: Directory of job.
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

    :param job: A job in any state.
    :param job_dir: Directory of job.
    :raises HTTPException: When job is not completed.
    :return: Directory of a completed job.
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

    :param path: Path to file that job has produced.
    :param job_dir: Directory with job output files.
    :raises HTTPException: When file is not found or is outside job directory.
    :return: The file content.
    """
    try:
        full_path = (job_dir / path).expanduser().resolve(strict=True)
        if not full_path.is_relative_to(job_dir):
            raise FileNotFoundError()
        # TODO if path == '' or path is directory then return file listing?
        # Similar to AWS S3 ListObjectsV2 or Webdav PROPFIND
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

    :param job_dir: Directory with job output files.
    :return: Content of standard output.
    """
    return retrieve_job_files("stdout.txt", job_dir)


@router.get("/{jobid}/stderr", response_class=FileResponse)
def retrieve_job_stderr(
    job_dir: Path = Depends(get_dir_of_completed_job),
) -> FileResponse:
    """Retrieve the jobs standard error.

    :param job_dir: Directory with job output files.
    :return: Content of standard error.
    """
    return retrieve_job_files("stderr.txt", job_dir)
