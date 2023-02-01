from typing import Awaitable, Callable

from fastapi import FastAPI

from bartender.config import build_config
from bartender.context import build_context, close_context
from bartender.db.session import make_engine, make_session_factory
from bartender.settings import settings


def _setup_db(app: FastAPI) -> None:  # pragma: no cover
    """Creates connection to the database.

    This function creates SQLAlchemy engine instance,
    session_factory for creating sessions
    and stores them in the application's state property.

    Args:
        app: fastAPI application.
    """
    app.state.db_engine = make_engine()
    app.state.db_session_factory = make_session_factory(app.state.db_engine)


def register_startup_event(
    app: FastAPI,
) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """Actions to run on application startup.

    This function uses fastAPI app to store data
    inthe state, such as db_engine.

    Args:
        app: the fastAPI application.

    Returns:
        function that actually performs actions.
    """

    @app.on_event("startup")
    async def _startup() -> None:  # noqa: WPS430
        _setup_db(app)
        _parse_context(app)

    return _startup


def register_shutdown_event(
    app: FastAPI,
) -> Callable[[], Awaitable[None]]:  # pragma: no cover
    """Actions to run on application's shutdown.

    Args:
        app: fastAPI application.

    Returns:
        function that actually performs actions.
    """

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # noqa: WPS430
        await app.state.db_engine.dispose()
        await _teardown_context(app)

    return _shutdown


def _parse_context(app: FastAPI) -> None:
    """Parse configuration and instantiate applications, schedulers and filesystems.

    Sets `app.state.config` and `app.state.context`.

    Args:
        app: fastAPI application.
    """
    config = build_config(settings.config_filename)
    app.state.config = config
    app.state.context = build_context(config)


async def _teardown_context(app: FastAPI) -> None:
    """Teardown schedulers and file systems.

    Args:
        app: fastAPI application.
    """
    await close_context(app.state.context)
