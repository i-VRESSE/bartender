from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import (
    APIKeyCookie,
    APIKeyQuery,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from starlette.status import (
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from bartender.user import JwtDecoder, User

header = HTTPBearer(bearerFormat="jwt", auto_error=False)
cookie = APIKeyCookie(name="bartenderToken", auto_error=False)
query = APIKeyQuery(name="token", auto_error=False)


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


def get_jwt_decoder(request: Request) -> JwtDecoder:
    """Get JWT decoder from app state.

    Args:
        request: current request.

    Raises:
        HTTPException: Internal server error 500 if JWT decoder is not setup.

    Returns:
        JWT decoder object
    """
    try:
        return request.app.state.jwt_decoder
    except AttributeError:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT decoder not setup",
        )


def current_user(
    apikey: Annotated[str, Depends(current_api_token)],
    jwt_decoder: Annotated[JwtDecoder, Depends(get_jwt_decoder)],
) -> User:
    """Current user based on API token.

    Args:
        apikey: API key
        jwt_decoder: JWT decoder

    Raises:
        HTTPException: Unauthorized 401 response if API key is invalid.
            Or internal server error 500 if JWT decoder is not setup.

    Returns:
        User
    """
    try:
        return jwt_decoder(apikey)
    except ExpiredSignatureError as exception:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=str(exception))
    except JWTClaimsError as exception:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=str(exception))
    except JWTError as exception:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail=str(exception))


CurrentUser = Annotated[User, Depends(current_user)]
