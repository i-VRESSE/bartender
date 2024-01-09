"""Filesystem module."""

from pathlib import Path
from typing import Literal

from bartender.config import ApplicatonConfiguration


def has_config_file(
    application: ApplicatonConfiguration,
    job_dir: Path,
) -> Literal[True]:
    """Check if config file required by application is present in job directory.

    Args:
        application: Name of application to check config file for.
        job_dir: In which directory to look.

    Raises:
        IndexError: When config file could not be found

    Returns:
        True when found.
    """
    app_config = application.config
    job_config = job_dir / app_config
    has = job_config.exists() and job_config.is_file()
    if not has:
        raise IndexError(
            f"Application requires config file called {app_config}, "
            "but was not found in upload",
        )
    return has
