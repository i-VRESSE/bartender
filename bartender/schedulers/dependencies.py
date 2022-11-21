from starlette.requests import Request

from bartender.config import Config
from bartender.schedulers.abstract import AbstractScheduler


def get_scheduler(request: Request) -> AbstractScheduler:
    """Retrieve job scheduler.

    :param request: current request.
    :return: A scheduler.
    """
    config: Config = request.app.config
    destinations = config.destinations.values()
    # TODO dont pick first scheduler
    destination = list(destinations)[0]
    return destination.scheduler
