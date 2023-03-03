from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bartender.db.dependencies import get_db_session
from bartender.db.models.user import OAuthAccount, User

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1


class UserDatabase(SQLAlchemyUserDatabase[User, UUID]):
    """Database adapter for SQLAlchemy with extra methods."""

    async def list(self, limit: int, offset: int) -> list[User]:
        """Get list of users.

        Args:
            limit: limit of users.
            offset: offset of users.

        Returns:
            list of users.
        """
        statement = select(self.user_table).limit(limit).offset(offset)
        results = await self.session.execute(statement)
        return results.unique().scalars().all()

    async def grant_role(self, user: User, role: str) -> None:
        """Grant a role to a user.

        Args:
            user: The user.
            role: The role.
        """
        if role not in user.roles:
            user.roles.append(role)
            await self.session.commit()
            await self.session.refresh(user)

    async def revoke_role(self, user: User, role: str) -> None:
        """Revoke a role to a user.

        Args:
            user: The user.
            role: The role.
        """
        user.roles.remove(role)
        await self.session.commit()
        await self.session.refresh(user)


async def get_user_db(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[UserDatabase, None]:
    """Factory method for accessing user table.

    Args:
        session: SQLAlchemy session

    Yields:
        Database adaptor
    """
    yield UserDatabase(session, User, OAuthAccount)
