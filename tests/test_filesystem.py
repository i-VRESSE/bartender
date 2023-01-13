from pathlib import Path

from bartender.filesystem.assemble_job import assemble_job


def test_assemble_job(job_root_dir: Path) -> None:
    """Test the assembly the job."""
    job_id = 1
    token = "mytoken"  # noqa: S105

    assemble_job(job_id, token, job_root_dir)

    job_dir = job_root_dir / str(job_id)
    meta_file = job_dir / "meta"
    assert job_dir.exists()
    assert meta_file.exists()
    body = meta_file.read_text()
    assert str(job_id) in body
    assert token in body
