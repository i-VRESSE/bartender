from typing import Annotated, AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Create and get database session.

    Args:
        request: current request.

    Yields:
        database session.
    """
    session: AsyncSession = request.app.state.db_session_factory()

    try:  # noqa: WPS501
        yield session
    finally:
        await session.commit()
        await session.close()


CurrentSession = Annotated[AsyncSession, Depends(get_db_session)]
