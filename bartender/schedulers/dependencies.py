from starlette.requests import Request

from bartender.schedulers.abstract import AbstractScheduler


def get_scheduler(request: Request) -> AbstractScheduler:
    """Retrieve job scheduler.

    :param request: current request.
    :return: A scheduler.
    """
    return request.app.scheduler
