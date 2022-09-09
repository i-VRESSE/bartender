"""Filesystem module."""

from bartender.settings import settings


def setup_job_root_dir() -> None:
    """Make sure job root dir exists.

    Job root dir is retrieved from settings.
    """
    job_root_dir = settings.job_root_dir
    job_root_dir.mkdir(exist_ok=True)
