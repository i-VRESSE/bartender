from os import getloadavg, sched_getaffinity

from fastapi import HTTPException
from starlette import status


def check_load(max_load: float = 1.0) -> None:
    """Check if machine load is too high.

    Args:
        max_load: Maximum load allowed.

    Raises:
        HTTPException: When machine load is too high.
    """
    nr_cpus = len(sched_getaffinity(0))
    load_avg_last_minute = getloadavg()[0] / nr_cpus
    if load_avg_last_minute > max_load:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine load is too high, please try again later.",
        )
