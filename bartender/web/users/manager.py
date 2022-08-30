from typing import AsyncGenerator
from uuid import UUID

from fastapi import Depends
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase

from bartender.db.dao.user_dao import get_user_db
from bartender.db.models.user import User
from bartender.settings import settings

# From app/users.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """The user manager."""

    reset_password_token_secret = settings.secret
    verification_token_secret = settings.secret

    # For on_* methods see
    # https://fastapi-users.github.io/fastapi-users/10.1/configuration/user-manager/


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase[User, UUID] = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    """Factory to get user manager.

    :param user_db: User database.
    :yield: The manager.
    """
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="/auth/jwt/login")

LIFETIME = 3600  # 1 hour


def get_jwt_strategy() -> JWTStrategy[User, UUID]:
    """Get jwt strategy.

    :return: The strategy.
    """
    return JWTStrategy(secret=settings.secret, lifetime_seconds=LIFETIME)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
