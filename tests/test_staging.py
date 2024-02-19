from pathlib import Path

import pytest

from bartender.config import ApplicatonConfiguration
from bartender.staging import create_job_dir, has_needed_files


@pytest.mark.anyio
async def test_create_job_dir(job_root_dir: Path) -> None:
    """Test the assembly the job."""
    job_id = 1

    await create_job_dir(job_id, job_root_dir)

    job_dir = job_root_dir / str(job_id)
    assert job_dir.exists()


class TestHasNeededFiles:
    @pytest.fixture
    def job_dir(self, tmp_path: Path) -> Path:
        return tmp_path

    @pytest.fixture
    def application(self) -> ApplicatonConfiguration:
        return ApplicatonConfiguration(
            command_template="wc config.ini data.csv",
            upload_needs=["config.ini", "data.csv"],
        )

    def test_has_needed_files_with_existing_files(
        self,
        job_dir: Path,
        application: ApplicatonConfiguration,
    ) -> None:
        # Create the needed files
        (job_dir / "config.ini").touch()
        (job_dir / "data.csv").touch()

        # Check if the files exist
        result = has_needed_files(application, job_dir)

        # Assert that the function returns True
        assert result is True

    def test_has_needed_files_with_missing_files(
        self,
        job_dir: Path,
        application: ApplicatonConfiguration,
    ) -> None:
        # Check if the files are missing
        with pytest.raises(IndexError):
            has_needed_files(application, job_dir)

    def test_has_needed_files_with_partial_missing_files(
        self,
        job_dir: Path,
        application: ApplicatonConfiguration,
    ) -> None:
        # Create one of the needed files
        (job_dir / "config.ini").touch()

        # Check if the files are missing
        with pytest.raises(IndexError):
            has_needed_files(application, job_dir)

    def test_has_needed_files_with_no_files_needed(
        self,
        job_dir: Path,
        application: ApplicatonConfiguration,
    ) -> None:
        # Remove the upload_needs list
        application.upload_needs = []

        # Check if the function returns True
        result = has_needed_files(application, job_dir)
        assert result is True
