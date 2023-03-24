
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bartender.settings import settings


def make_engine() -> AsyncEngine:
    """This function creates SQLAlchemy engine instance.

    Returns:
        async engine
    """
    return create_async_engine(str(settings.db_url), echo=settings.db_echo)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create session_factory for creating sessions.

    Args:
        engine: async engine

    Returns:
        session factory
    """
    # TODO replace with async sessionmaker
    # see https://fastapi-users.github.io/fastapi-users/10.4/configuration/full-example/
    return async_sessionmaker(engine, expire_on_commit=False)
