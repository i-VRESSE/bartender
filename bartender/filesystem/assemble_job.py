# This puts the files in the directories

from bartender.settings import settings


# TODO: Make this async
def assemble_job(job_id: int) -> None:
    """
    Assembly the job.

    :param job_id: id of the job.
    """
    job_dir = settings.job_root_dir / str(job_id)
    # TODO: `exist_ok` is only there for testing purposes.
    job_dir.mkdir(parents=True, exist_ok=True)
    id_file = job_dir / "id"
    id_file.write_text(str(job_id))
