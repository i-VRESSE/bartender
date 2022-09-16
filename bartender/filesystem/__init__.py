"""Filesystem module."""

from pathlib import Path

from bartender.settings import settings


def setup_job_root_dir() -> None:
    """Make sure job root dir exists.

    Job root dir is retrieved from settings.
    """
    job_root_dir = settings.job_root_dir
    job_root_dir.mkdir(exist_ok=True)


def has_config_file(application: str, job_dir: Path) -> bool:
    """Check if config file required by application is present in job directory.

    :param application: Application to check config file for.
    :param job_dir: In which directory to look.
    :raises IndexError: When config file could not be found
    :return: True when found.
    """
    app_config = settings.applications[application].config
    job_config = job_dir / app_config
    has = job_config.exists() and job_config.is_file()
    if not has:
        raise IndexError(
            f"Application requires config file called ${app_config}, "
            "but was not found in upload",
        )
    return has
