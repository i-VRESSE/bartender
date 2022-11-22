import logging
from pathlib import Path
from typing import Awaitable, Callable

from fastapi import FastAPI

from bartender.config import build_config
from bartender.db.session import make_engine, make_session_factory
from bartender.destinations import Destination
from bartender.settings import settings

logger = logging.getLogger(__name__)


def _setup_db(app: FastAPI) -> None:  # pragma: no cover
    """
    Creates connection to the database.

    This function creates SQLAlchemy engine instance,
    session_factory for creating sessions
    and stores them in the application's state property.

    :param app: fastAPI application.
    """
    app.state.db_engine = make_engine()
    app.state.db_session_factory = make_session_factory(app.state.db_engine)


def register_startup_event(
    app: FastAPI,
) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """
    Actions to run on application startup.

    This function uses fastAPI app to store data
    inthe state, such as db_engine.

    :param app: the fastAPI application.
    :return: function that actually performs actions.
    """

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: WPS430
        _setup_db(app)
        _parse_config(app)

    return _startup


def register_shutdown_event(
    app: FastAPI,
) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """
    Actions to run on application's shutdown.

    :param app: fastAPI application.
    :return: function that actually performs actions.
    """

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: WPS430
        await app.state.db_engine.dispose()
        await _teardown_confg(app)

    return _shutdown


def _parse_config(app: FastAPI) -> None:
    """Parse configuration and instantiate applications, schedulers and filesystems.

    Sets `app.state.config`.

    :param app: fastAPI application.
    """
    try:
        config = build_config(settings.config_filename)
        # Make sure job root dir exists.
        config.job_root_dir.mkdir(exist_ok=True)
        app.state.config = config
    except FileNotFoundError:
        fn = settings.config_filename
        logger.warn(f"Unable to find {fn} falling back to config-example.yaml")
        app.state.config = build_config(Path("config-example.yaml"))


async def _teardown_confg(app: FastAPI) -> None:
    """Teardown schedulers and file systems.

    :param app: fastAPI application.
    """
    destinations: dict[str, Destination] = app.state.config.destinations
    for destination in destinations.values():
        await destination.scheduler.close()
        if destination.filesystem is not None:
            destination.filesystem.close()
