import asyncio
from os import symlink
from pathlib import Path

from bartender.config import build_config
from bartender.db.dao.job_dao import JobDAO
from bartender.db.session import make_engine, make_session_factory


def link_job(
    directory: Path,
    submitter: str,
    application: str,
    config: Path,
    destination: str = "local",
) -> None:
    """Link external directory as job.

    Args:
        directory: Directory to link as job
        submitter: Submitter of job
        application: Application of job
        config: Configuration with schedulers that need arq workers
        destination: Destination of job
    """
    validated_config = build_config(config)
    job_root_dir = validated_config.job_root_dir
    name = directory.name

    # Create job in db
    job_id = asyncio.run(
        create_job_in_db(name, application, submitter, destination),
    )

    # Sym link directory to job directory
    job_dir = job_root_dir / str(job_id)
    symlink(directory.absolute(), job_dir)
    print(job_id)  # noqa: WPS421 -- user feedback


async def create_job_in_db(
    name: str,
    application: str,
    submitter: str,
    destination: str,
) -> int:
    """
    Create a job in the database.

    Args:
        name: The name of the job.
        application: The application associated with the job.
        submitter: The submitter of the job.
        destination: The destination of the job.

    Returns:
        The ID of the created job.

    Raises:
        IndexError: If failed to create a database entry for the job.
    """
    engine = make_engine()
    factory = make_session_factory(engine)
    async with factory() as session:
        dao = JobDAO(session)
        job_id = await dao.create_job(name, application, submitter)
        if job_id is None:
            raise IndexError("Failed to create database entry for job")
        await dao.update_internal_job_id(
            job_id,
            internal_job_id=name,
            destination=destination,
        )
        await dao.update_job_state(job_id, "ok")
        return job_id
