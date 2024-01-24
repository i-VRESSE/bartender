"""Filesystem module."""

from pathlib import Path
from typing import Literal

from bartender.config import ApplicatonConfiguration


def has_needed_files(
    application: ApplicatonConfiguration,
    job_dir: Path,
) -> Literal[True]:
    """Check if files required by application are present in job directory.

    Args:
        application: Name of application to check config file for.
        job_dir: In which directory to look.

    Raises:
        IndexError: When one or more needed files can not be found

    Returns:
        True when found.
    """
    if not application.upload_needs:
        return True
    missing_files = []
    for needed_file in application.upload_needs.values():
        file = job_dir / needed_file
        file_exists = file.exists() and file.is_file()
        if not file_exists:
            missing_files.append(needed_file)
    if missing_files:
        raise IndexError(
            f"Application requires files {missing_files}, "
            "but where not found in uploaded zip archive",
        )
    return True
