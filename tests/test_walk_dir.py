from pathlib import Path

import pytest

from bartender.walk_dir import DirectoryItem, walk_dir


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

    @pytest.mark.anyio
    async def test_given_symlink_as_job_dir(self, tmp_path: Path) -> None:
        (tmp_path / "somedir").mkdir()
        (tmp_path / "somedir" / "somefile").write_text("sometext")
        (tmp_path / "symlink").symlink_to(tmp_path / "somedir")

        result = await walk_dir(tmp_path / "symlink", tmp_path, max_depth=2)

        expected = DirectoryItem(
            name="symlink",
            path=Path("symlink"),
            is_dir=True,
            is_file=False,
            children=[
                DirectoryItem(
                    name="somefile",
                    path=Path("symlink/somefile"),
                    is_dir=False,
                    is_file=True,
                ),
            ],
        )
        assert result == expected
