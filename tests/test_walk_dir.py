from collections.abc import AsyncIterable
from datetime import datetime
from pathlib import Path

import pytest
from stream_zip import ZIP_32

from bartender.walk_dir import (
    DirectoryItem,
    exclude_filter,
    read_only_file_mode,
    walk_dir,
    walk_dir_generator,
)


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


async def slurp_content(content_iter: AsyncIterable[bytes]) -> bytes:
    return b"".join([chunk async for chunk in content_iter])


@pytest.mark.anyio
class TestWalkDirGenerator:
    async def test_given_empty_dir_yields_nothing(self, tmp_path: Path) -> None:
        results = [entry async for entry in walk_dir_generator(tmp_path)]
        assert not results

    async def test_given_single_file_yields_one_entry(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        nr_files = 0
        async for entry in walk_dir_generator(tmp_path):
            nr_files += 1
            name, mtime, mode, method, content_iter = entry
            assert name == "test.txt"
            assert isinstance(mtime, datetime)
            assert mode == read_only_file_mode
            assert method == ZIP_32
            contents = await slurp_content(content_iter)
            assert contents == b"content"

        assert nr_files == 1

    async def test_given_nested_files_yields_all(self, tmp_path: Path) -> None:
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "file1.txt").write_text("content1")
        (tmp_path / "dir1" / "dir2").mkdir()
        (tmp_path / "dir1" / "dir2" / "file2.txt").write_text("content2")

        files = []
        async for entry in walk_dir_generator(tmp_path):
            name, mtime, mode, method, content_iter = entry
            assert isinstance(mtime, datetime)
            assert mode == read_only_file_mode
            assert method == ZIP_32
            contents = await slurp_content(content_iter)
            files.append((name, contents))

        assert len(files) == 2
        assert ("dir1/file1.txt", b"content1") in files
        assert ("dir1/dir2/file2.txt", b"content2") in files

    async def test_exclude_dir(self, tmp_path: Path) -> None:
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "file1.txt").write_text("content1")
        # Follow should be excluded
        (tmp_path / "dir1" / "dir2").mkdir()
        (tmp_path / "dir1" / "dir2" / "file2.txt").write_text("content2")

        files = []
        async for entry in walk_dir_generator(tmp_path, exclude_filter(["dir1/dir2"])):
            name, mtime, mode, method, content_iter = entry
            assert isinstance(mtime, datetime)
            assert mode == read_only_file_mode
            assert method == ZIP_32
            contents = await slurp_content(content_iter)

            files.append((name, contents))

        assert len(files) == 1
        assert ("dir1/file1.txt", b"content1") in files

    async def test_exclude_file(self, tmp_path: Path) -> None:
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "file1.txt").write_text("content1")
        # Follow should be excluded
        (tmp_path / "dir1" / "file2.txt").write_text("content2")

        files = []
        async for entry in walk_dir_generator(tmp_path, exclude_filter(["file2.txt"])):
            name, mtime, mode, method, content_iter = entry
            assert isinstance(mtime, datetime)
            assert mode == read_only_file_mode
            assert method == ZIP_32
            contents = await slurp_content(content_iter)

            files.append((name, contents))

        assert len(files) == 1
        assert ("dir1/file1.txt", b"content1") in files

    async def test_exclude_files_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "dir1").mkdir()
        (tmp_path / "dir1" / "file1.txt").write_text("content1")
        (tmp_path / "dir1" / "file2.txt").write_text("content2")
        (tmp_path / "dir1" / "dir2").mkdir()
        (tmp_path / "dir1" / "dir2" / "file3.txt").write_text("content3")
        (tmp_path / "dir1" / "dir2" / "file4.txt").write_text("content4")
        (tmp_path / "dir3").mkdir()
        (tmp_path / "dir3" / "file5.txt").write_text("content5")

        files = []
        wfilter = exclude_filter(["file2.txt", "file4.txt", "dir2", "dir3"])
        async for entry in walk_dir_generator(tmp_path, wfilter):
            name, mtime, mode, method, content_iter = entry
            assert isinstance(mtime, datetime)
            assert mode == read_only_file_mode
            assert method == ZIP_32
            contents = await slurp_content(content_iter)
            files.append((name, contents))

        assert len(files) == 1
        assert ("dir1/file1.txt", b"content1") in files
