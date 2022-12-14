from typing import Any, AsyncGenerator, Optional
from uuid import UUID

from fastapi import Depends, Response
from fastapi.security import HTTPBearer
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.authentication.transport.base import (
    Transport,
    TransportLogoutNotSupportedError,
)
from fastapi_users.authentication.transport.bearer import BearerResponse
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from httpx_oauth.clients.github import GitHubOAuth2

from bartender.db.dao.user_dao import get_user_db
from bartender.db.models.user import User
from bartender.settings import settings
from bartender.web.users.orcid import OrcidOAuth2

# From app/users.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
# From app/users.py
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth/#sqlalchemy_1

github_oauth_client: Optional[GitHubOAuth2] = None
if settings.github_client_id != "":
    github_oauth_client = GitHubOAuth2(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
    )

orcidsandbox_oauth_client: Optional[OrcidOAuth2] = None
if settings.orcidsandbox_client_id != "":
    orcidsandbox_oauth_client = OrcidOAuth2(
        client_id=settings.orcidsandbox_client_id,
        client_secret=settings.orcidsandbox_client_secret,
        is_sandbox=True,
    )

orcid_oauth_client: Optional[OrcidOAuth2] = None
if settings.orcid_client_id != "":
    orcid_oauth_client = OrcidOAuth2(
        client_id=settings.orcid_client_id,
        client_secret=settings.orcid_client_secret,
    )


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


LIFETIME = 3600  # 1 hour


def get_jwt_strategy() -> JWTStrategy[User, UUID]:
    """Get jwt strategy.

    :return: The strategy.
    """
    return JWTStrategy(secret=settings.secret, lifetime_seconds=LIFETIME)


local_auth_backend = AuthenticationBackend(
    name="local",
    transport=BearerTransport(tokenUrl="/auth/jwt/login"),
    get_strategy=get_jwt_strategy,
)


class HTTPBearerTransport(Transport):
    """After social login (Orcid, GitHub) you can use the JWT token to auth yourself."""

    scheme: HTTPBearer

    def __init__(self) -> None:
        self.scheme = HTTPBearer(bearerFormat="jwt", auto_error=False)

    async def get_login_response(self, token: str, response: Response) -> Any:
        """Returns token after login.

        :param token: The token
        :param response: The response
        :return: Token as JSON
        """
        return BearerResponse(access_token=token, token_type="bearer")  # noqa: S106

    async def get_logout_response(self, response: Response) -> Any:
        """Logout response.

        :param response: The response
        :raises TransportLogoutNotSupportedError: Always raises as JWT can not logout
        """
        raise TransportLogoutNotSupportedError()


remote_auth_backend = AuthenticationBackend(
    name="remote",
    transport=HTTPBearerTransport(),
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [local_auth_backend, remote_auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)

# TODO Token used by a job should be valid for as long as job can run.

API_TOKEN_LIFETIME = 14400  # 4 hours


async def current_api_token(user: User = Depends(current_active_user)) -> str:
    """Generate token that job can use to talk to bartender service.

    :param user: User that is currently logged in.
    :return: The token that can be put in HTTP header `Authorization: Bearer <token>`.
    """
    strategy: JWTStrategy[User, UUID] = JWTStrategy(
        secret=settings.secret,
        lifetime_seconds=API_TOKEN_LIFETIME,
    )
    return await strategy.write_token(user)
