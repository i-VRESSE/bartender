from pathlib import Path

from bartender.filesystem.assemble_job import assemble_job


def test_assemble_job(job_root_dir: Path) -> None:
    """Test the assembly the job."""
    job_id = 1

    assemble_job(job_id)

    job_dir = job_root_dir / str(job_id)
    id_file = job_dir / "id"
    assert job_dir.exists()
    assert id_file.exists()
    assert str(job_id) == id_file.read_text()
