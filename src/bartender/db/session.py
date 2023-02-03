from asyncio import current_task

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from bartender.settings import settings


def make_engine() -> AsyncEngine:
    """This function creates SQLAlchemy engine instance.

    Returns:
        async engine
    """
    return create_async_engine(str(settings.db_url), echo=settings.db_echo)


def make_session_factory(engine: AsyncEngine) -> async_scoped_session:
    """Create session_factory for creating sessions.

    Args:
        engine: async engine

    Returns:
        session factory
    """
    return async_scoped_session(
        sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession,
        ),
        scopefunc=current_task,
    )
