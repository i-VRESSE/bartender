from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from bartender.config import ApplicatonConfiguration, Config
from bartender.destinations import Destination
from bartender.destinations import build as build_destinations
from bartender.picker import DestinationPicker, import_picker


# TODO also use pydantic.BaseModel here,
# but mypy complains if BaseModel is used
@dataclass
class Context:
    """Context for web service."""

    applications: dict[str, ApplicatonConfiguration]
    destinations: dict[str, Destination]
    job_root_dir: Path
    destination_picker: DestinationPicker


def build_context(config: Config) -> Context:
    """Parses a plain configuration dict to a context instance.

    :param config: A plain configuration dict
    :return: A config instance.
    """
    return Context(
        applications=config.applications,
        job_root_dir=config.job_root_dir,
        destinations=build_destinations(config.destinations),
        destination_picker=import_picker(config.destination_picker),
    )


def get_context(request: Request) -> Context:
    """Get context based on current request.

    :param request: The current FastAPI request.
    :return: The context.
    """
    return request.app.state.context


async def close_context(context: Context) -> None:
    """Closes destinations in context.

    A destination might have a remote connection that needs to be cleaned-up.

    :param context: The context.
    """
    destinations: dict[str, Destination] = context.destinations
    for destination in destinations.values():
        await destination.close()
