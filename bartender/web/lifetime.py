from typing import Awaitable, Callable

from fastapi import FastAPI

from bartender.db.session import make_engine, make_session_factory
from bartender.filesystem import setup_job_root_dir
from bartender.schedulers.memory import MemoryScheduler
from bartender.settings import settings


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
        setup_job_root_dir()
        _setup_scheduler(app)

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
        await _teardown_scheduler(app)

    return _shutdown


def _setup_scheduler(app: FastAPI) -> None:
    """Create scheduler.

    :param app: fastAPI application.
    """
    app.state.scheduler = MemoryScheduler(settings.scheduler_slots)


async def _teardown_scheduler(app: FastAPI) -> None:
    """Teardown scheduler.

    :param app: fastAPI application.
    """
    await app.state.scheduler.close()
