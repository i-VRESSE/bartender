# This puts the files in the directories

from pathlib import Path

from bartender.settings import settings


# TODO: Make this async
def assemble_job(job_id: int, job_token: str) -> Path:
    """
    Assembly the job.

    Create job directory and metadata file.
    Metadata file contains job id and token.

    :param job_id: id of the job.
    :param job_token: Token that can be used to talk to bartender service.
    :return: Directory of job.
    """
    job_dir = settings.job_root_dir / str(job_id)
    job_dir.mkdir()
    meta_file = job_dir / "meta"
    body = f"{job_id}\n{job_token}\n"
    meta_file.write_text(body)
    return job_dir
