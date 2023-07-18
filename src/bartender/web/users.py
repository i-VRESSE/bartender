from typing import Annotated, Optional, Sequence

from fastapi import Depends, HTTPException
from fastapi.security import (
    APIKeyCookie,
    APIKeyQuery,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jose import jwt
from pydantic import BaseModel
from starlette.status import HTTP_403_FORBIDDEN

from bartender.settings import settings

header = HTTPBearer(bearerFormat="jwt", auto_error=False)
cookie = APIKeyCookie(name="bartenderToken", auto_error=False)
query = APIKeyQuery(name="token", auto_error=False)


class User(BaseModel):
    """User model."""

    username: str
    roles: Sequence[str]
    apikey: str


def current_api_token(
    apikey: Annotated[Optional[HTTPAuthorizationCredentials], Depends(header)],
    apikey_from_cookie: Annotated[Optional[str], Depends(cookie)],
    apikey_from_query: Annotated[Optional[str], Depends(query)],
) -> str:
    """Retrieve API token from header, cookie or query.

    Args:
        apikey: API key from header
        apikey_from_cookie: API key from cookie
        apikey_from_query: API key from query

    Raises:
        HTTPException: Forbidden 403 response if API key is not found.

    Returns:
        API key
    """
    if apikey_from_cookie:
        # Using api key inside cookie does not work with Swagger UI.
        # however curl example works
        return apikey_from_cookie
    if apikey_from_query:
        return apikey_from_query
    if apikey:
        return apikey.credentials
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not authenticated")


def current_user(
    apikey: Annotated[str, Depends(current_api_token)],
) -> User:
    """Current user based on API token.

    Args:
        apikey: API key

    Returns:
        User
    """
    public_key = settings.jwt_key
    # TODO catch exceptions and raise 40x error
    options = {
        "verify_signature": True,
        "verify_aud": True,
        "verify_iat": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iss": True,
        "verify_sub": True,
        "verify_jti": True,
        "verify_at_hash": True,
        "require_aud": False,
        "require_iat": False,
        "require_exp": True,
        "require_nbf": False,
        "require_iss": True,
        "require_sub": True,
        "require_jti": False,
        "require_at_hash": False,
        "leeway": 0,
    }
    data = jwt.decode(
        apikey,
        public_key,
        algorithms=["RS256"],
        # TODO verify more besides exp and public key
        # like aud, iss, nbf
        options=options,
    )
    return User(
        username=data["sub"],
        roles=data["roles"],
        apikey=apikey,
        # TODO store issuer in db so we can see from where job was submitted?
    )


CurrentUser = Annotated[User, Depends(current_user)]
