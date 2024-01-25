from pathlib import Path

import pytest

from bartender.config import ApplicatonConfiguration
from bartender.filesystem import has_needed_files
from bartender.filesystem.assemble_job import assemble_job
from bartender.filesystem.walk_dir import DirectoryItem, walk_dir


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


class TestWalkDir:
    @pytest.mark.anyio
    async def test_given_empty_dir(self, tmp_path: Path) -> None:
        result = await walk_dir(tmp_path, tmp_path)

        expected = DirectoryItem(name="", path=Path(), is_dir=True, is_file=False)
        assert result == expected

    @pytest.mark.anyio
    async def test_given_single_file(self, tmp_path: Path) -> None:
        (tmp_path / "somefile").write_text("sometext")

        result = await walk_dir(tmp_path, tmp_path)

        expected = DirectoryItem(
            name="",
            path=Path(),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somefile",
                    path=Path("somefile"),
                    is_dir=False,
                    is_file=True,
                ),
            ],
        )
        assert result == expected

    @pytest.mark.anyio
    async def test_given_single_dir(self, tmp_path: Path) -> None:
        (tmp_path / "somedir").mkdir()

        result = await walk_dir(tmp_path, tmp_path)

        expected = DirectoryItem(
            name="",
            path=Path(),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somedir",
                    path=Path("somedir"),
                    is_dir=True,
                    is_file=False,
                ),
            ],
        )
        assert result == expected

    @pytest.mark.anyio
    async def test_given_single_dir_with_file_and_depth1(self, tmp_path: Path) -> None:
        (tmp_path / "somedir").mkdir()
        (tmp_path / "somedir" / "somefile").write_text("sometext")

        result = await walk_dir(tmp_path, tmp_path)

        expected = DirectoryItem(
            name="",
            path=Path(),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somedir",
                    path=Path("somedir"),
                    is_dir=True,
                    is_file=False,
                ),
            ],
        )
        assert result == expected

    @pytest.mark.anyio
    async def test_given_single_dir_with_file_and_depth2(self, tmp_path: Path) -> None:
        (tmp_path / "somedir").mkdir()
        (tmp_path / "somedir" / "somefile").write_text("sometext")

        result = await walk_dir(tmp_path, tmp_path, max_depth=2)

        expected = DirectoryItem(
            name="",
            path=Path(),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somedir",
                    path=Path("somedir"),
                    is_dir=True,
                    is_file=False,
                    children=[
                        DirectoryItem(
                            name="somefile",
                            path=Path("somedir/somefile"),
                            is_dir=False,
                            is_file=True,
                        ),
                    ],
                ),
            ],
        )
        assert result == expected

    @pytest.mark.anyio
    async def test_given_single_dir_with_file_and_dir_as_subdir(
        self,
        tmp_path: Path,
    ) -> None:
        dir1 = tmp_path / "somedir"
        dir1.mkdir()
        (dir1 / "somefile").write_text("sometext")

        result = await walk_dir(dir1, tmp_path, max_depth=2)

        expected = DirectoryItem(
            name="somedir",
            path=Path("somedir"),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somefile",
                    path=Path("somedir/somefile"),
                    is_dir=False,
                    is_file=True,
                ),
            ],
        )
        assert result == expected
