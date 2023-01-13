from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from bartender.db.dependencies import get_db_session
from bartender.db.models.user import OAuthAccount, User

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1


async def get_user_db(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase[User, UUID], None]:
    """Factory method for accessing user table.

    :param session: SQLAlchemy session
    :yield: Database adaptor
    """
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
