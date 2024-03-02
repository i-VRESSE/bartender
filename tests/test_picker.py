from pathlib import Path
from textwrap import dedent

import pytest

from bartender.context import ApplicatonConfiguration, Context
from bartender.destinations import Destination
from bartender.picker import PickRound, import_picker, pick_first
from bartender.user import User


@pytest.fixture
def user() -> User:
    return User(
        username="user1",
        apikey="apikey1",
    )


class TestPickFirst:
    @pytest.mark.anyio
    async def test_with2destinations_returns_first(
        self,
        demo_destination: Destination,
        user: User,
    ) -> None:
        context = Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command_template="uptime"),
            },
            destinations={
                "d1": demo_destination,
                "d2": demo_destination,
            },
            job_root_dir=Path("/jobs"),
        )

        actual = pick_first(context.job_root_dir / "job1", "app1", user, context)

        expected = "d1"
        assert actual == expected

    @pytest.mark.anyio
    async def test_nodestintations_returns_indexerror(self, user: User) -> None:
        context = Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command_template="uptime"),
            },
            destinations={},
            job_root_dir=Path("/jobs"),
        )

        with pytest.raises(IndexError):
            pick_first(context.job_root_dir / "job1", "app1", user, context)


class TestPickRoundWith2Destinations:
    @pytest.fixture
    async def context(self, demo_destination: Destination) -> Context:
        return Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command_template="uptime"),
            },
            destinations={
                "d1": demo_destination,
                "d2": demo_destination,
            },
            job_root_dir=Path("/jobs"),
        )

    @pytest.mark.anyio
    async def test_firstcall_returns_first(self, context: Context, user: User) -> None:
        picker = PickRound()
        actual = picker(context.job_root_dir / "job1", "app1", user, context)

        expected = "d1"
        assert actual == expected

    @pytest.mark.anyio
    async def test_secondcall_returns_second(
        self,
        context: Context,
        user: User,
    ) -> None:
        picker = PickRound()
        # first call
        picker(context.job_root_dir / "job1", "app1", user, context)
        # second call
        actual = picker(context.job_root_dir / "job1", "app1", user, context)

        expected = "d2"
        assert actual == expected

    @pytest.mark.anyio
    async def test_thirdcall_returns_first(self, context: Context, user: User) -> None:
        picker = PickRound()
        # 1st call
        picker(context.job_root_dir / "job1", "app1", user, context)
        # 2nd call
        picker(context.job_root_dir / "job1", "app1", user, context)
        # 3rd call
        actual = picker(context.job_root_dir / "job1", "app1", user, context)

        expected = "d1"
        assert actual == expected


def test_import_picker_module() -> None:
    fn = import_picker("bartender.picker:pick_first")
    assert fn.__name__ == "pick_first"


def test_import_picker_file(
    tmp_path: Path,
    user: User,
) -> None:
    code = """\
        def mypicker(job_dir, application_name, submitter, context):
            return "mydestination"
    """
    path = tmp_path / "mymodule.py"
    path.write_text(dedent(code))

    fn = import_picker(f"{path}:mypicker")
    context = Context(
        destination_picker=fn,
        applications={},
        destinations={},
        job_root_dir=tmp_path,
    )
    result = fn(tmp_path, "someapp", user, context)
    assert result == "mydestination"
