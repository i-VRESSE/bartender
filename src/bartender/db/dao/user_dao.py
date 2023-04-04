from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select

from bartender.db.dependencies import CurrentSession
from bartender.db.models.user import OAuthAccount, User

# From app/db.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1


class UserDatabase(SQLAlchemyUserDatabase[User, UUID]):
    """Class for accessing user tables.

    Extends fastapi_users.SQLAlchemyUserDatabase see
    https://github.com/fastapi-users/fastapi-users-db-sqlalchemy/blob/main/fastapi_users_db_sqlalchemy/__init__.py#L96
    """

    async def list(self, limit: int, offset: int) -> list[User]:
        """Get list of users.

        Args:
            limit: limit of users.
            offset: offset of users.

        Returns:
            list of users.
        """
        statement = select(self.user_table).limit(limit).offset(offset)
        results = await self.session.scalars(statement)
        return list(results.unique().all())

    async def assign_role(self, user: User, role: str) -> None:
        """Assign a role to a user.

        Args:
            user: The user.
            role: The role.
        """
        if role not in user.roles:
            user.roles.append(role)
            await self.session.commit()
            await self.session.refresh(user)

    async def unassign_role(self, user: User, role: str) -> None:
        """Unassign a role to a user.

        Args:
            user: The user.
            role: The role.
        """
        if role in user.roles:
            user.roles.remove(role)
            await self.session.commit()
            await self.session.refresh(user)

    async def give_super_powers(self, user: User) -> None:
        """Give user super powers.

        Args:
            user (User): The user.
        """
        await self.update(user, {"is_superuser": True})


async def get_user_db(
    session: CurrentSession,
) -> AsyncGenerator[UserDatabase, None]:
    """Factory method for accessing user table.

    Args:
        session: SQLAlchemy session

    Yields:
        Database adaptor
    """
    yield UserDatabase(session, User, OAuthAccount)


CurrentUserDatabase = Annotated[UserDatabase, Depends(get_user_db)]
