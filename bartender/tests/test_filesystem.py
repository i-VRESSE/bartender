from bartender.filesystem.assemble_job import assemble_job
from bartender.settings import settings


def test_assemble_job() -> None:
    """Test the assembly the job."""
    job_id = 1
    assemble_job(job_id)
    job_dir = settings.job_root_dir / str(job_id)
    id_file = job_dir / "id"
    assert job_dir.exists()
    assert id_file.exists()
