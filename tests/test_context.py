from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from bartender.config import ApplicatonConfiguration, Config
from bartender.context import Context, build_context, close_context, get_context
from bartender.destinations import Destination, DestinationConfig
from bartender.filesystems.local import LocalFileSystemConfig
from bartender.picker import pick_first
from bartender.schedulers.memory import MemorySchedulerConfig


@pytest.mark.anyio
async def test_build_minimal(
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
    demo_context: Context,
) -> None:
    try:
        config = Config(
            applications=demo_applications,
            job_root_dir=job_root_dir,
            destinations={
                "dest1": DestinationConfig(
                    scheduler=MemorySchedulerConfig(),
                    filesystem=LocalFileSystemConfig(),
                ),
            },
        )

        result = build_context(config)

        expected = demo_context
        assert result == expected
    finally:
        await result.destinations["dest1"].scheduler.close()


def test_get_context(demo_context: Context) -> None:
    fake_request = MagicMock()
    fake_request.app.state.context = demo_context

    context = get_context(fake_request)

    expected = demo_context
    assert context == expected


@pytest.mark.anyio
async def test_close_context(
    job_root_dir: Path,
    demo_applications: dict[str, ApplicatonConfiguration],
) -> None:
    dest1 = MagicMock(Destination)
    dest1.close = AsyncMock()

    context = Context(
        applications=demo_applications,
        job_root_dir=job_root_dir,
        destination_picker=pick_first,
        destinations={"dest1": dest1},
    )

    await close_context(context)

    dest1.close.assert_called_once_with()
