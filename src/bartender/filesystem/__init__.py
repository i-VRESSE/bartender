"""Filesystem module."""

from pathlib import Path
from typing import Literal

from bartender.config import ApplicatonConfiguration


def has_config_file(
    application: ApplicatonConfiguration,
    job_dir: Path,
) -> Literal[True]:
    """Check if config file required by application is present in job directory.

    :param application: Name of application to check config file for.
    :param job_dir: In which directory to look.
    :raises IndexError: When config file could not be found
    :return: True when found.
    """
    app_config = application.config
    job_config = job_dir / app_config
    has = job_config.exists() and job_config.is_file()
    if not has:
        raise IndexError(
            f"Application requires config file called ${app_config}, "
            "but was not found in upload",
        )
    return has