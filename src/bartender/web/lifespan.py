from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from bartender.config import build_config
from bartender.context import build_context, close_context
from bartender.db.session import make_engine, make_session_factory
from bartender.filesystems.queue import (
    setup_file_staging_queue,
    teardown_file_staging_queue,
)
from bartender.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Logic which runs on application's startup and shutdown.

    Args:
        app: fastAPI application.

    Yields:
        Nothing.
    """
    _setup_db(app)
    _parse_context(app)
    setup_file_staging_queue(app)
    yield
    await app.state.db_engine.dispose()
    await close_context(app.state.context)
    await teardown_file_staging_queue(app)


def _setup_db(app: FastAPI) -> None:  # pragma: no cover
    """Creates connection to the database.

    This function creates SQLAlchemy engine instance, session_factory for
    creating sessions and stores them in the application's state property.

    Args:
        app: fastAPI application.
    """
    app.state.db_engine = make_engine()
    app.state.db_session_factory = make_session_factory(app.state.db_engine)


def _parse_context(app: FastAPI) -> None:
    """Parse configuration and instantiate applications, schedulers and filesystems.

    Sets `app.state.config` and `app.state.context`.

    Args:
        app: fastAPI application.
    """
    config = build_config(settings.config_filename)
    app.state.config = config
    app.state.context = build_context(config)