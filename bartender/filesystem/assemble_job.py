# This puts the files in the directories

from bartender.settings import settings


# TODO: Make this async
def assemble_job(job_id: int, job_token: str) -> None:
    """
    Assembly the job.

    Create job directory and metadata file.
    Metadata file contains job id and token.

    :param job_id: id of the job.
    :param job_token: Token that can be used to talk to bartender service.
    """
    job_dir = settings.job_root_dir / str(job_id)
    # TODO: `exist_ok` is only there for testing purposes.
    job_dir.mkdir(parents=True, exist_ok=True)
    meta_file = job_dir / "meta"
    body = f"{job_id}\n{job_token}\n"
    meta_file.write_text(body)
