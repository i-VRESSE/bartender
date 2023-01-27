from pathlib import Path

import pytest

from bartender.context import ApplicatonConfiguration, Context
from bartender.destinations import Destination
from bartender.picker import PickRound, pick_first


class TestPickFirst:
    @pytest.mark.anyio
    async def test_with2destinations_returns_first(
        self,
        demo_destination: Destination,
    ) -> None:
        context = Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
            },
            destinations={
                "d1": demo_destination,
                "d2": demo_destination,
            },
            job_root_dir=Path("/jobs"),
        )
        actual = pick_first(context.job_root_dir / "job1", "app1", context)

        expected = "d1"
        assert actual == expected

    @pytest.mark.anyio
    async def test_nodestintations_returns_indexerror(self) -> None:
        context = Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
            },
            destinations={},
            job_root_dir=Path("/jobs"),
        )

        with pytest.raises(IndexError):
            pick_first(context.job_root_dir / "job1", "app1", context)


class TestPickRoundWith2Destinations:
    @pytest.fixture
    async def context(self, demo_destination: Destination) -> Context:
        return Context(
            destination_picker=pick_first,
            applications={
                "app1": ApplicatonConfiguration(command="echo", config="/etc/passwd"),
            },
            destinations={
                "d1": demo_destination,
                "d2": demo_destination,
            },
            job_root_dir=Path("/jobs"),
        )

    @pytest.mark.anyio
    async def test_firstcall_returns_first(self, context: Context) -> None:
        picker = PickRound()
        actual = picker(context.job_root_dir / "job1", "app1", context)

        expected = "d1"
        assert actual == expected

    @pytest.mark.anyio
    async def test_secondcall_returns_second(self, context: Context) -> None:
        picker = PickRound()
        # first call
        picker(context.job_root_dir / "job1", "app1", context)
        # second call
        actual = picker(context.job_root_dir / "job1", "app1", context)

        expected = "d2"
        assert actual == expected

    @pytest.mark.anyio
    async def test_thirdcall_returns_first(self, context: Context) -> None:
        picker = PickRound()
        # 1st call
        picker(context.job_root_dir / "job1", "app1", context)
        # 2nd call
        picker(context.job_root_dir / "job1", "app1", context)
        # 3rd call
        actual = picker(context.job_root_dir / "job1", "app1", context)

        expected = "d1"
        assert actual == expected
