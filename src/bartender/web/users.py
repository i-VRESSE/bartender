from typing import Annotated, Optional, Sequence
from fastapi import Depends, HTTPException
import jwt
from pydantic import BaseModel
from bartender.settings import settings
from fastapi.security import HTTPBearer, APIKeyCookie, APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN

header = HTTPBearer(bearerFormat='jwt', auto_error=False)
cookie = APIKeyCookie(name="bartenderToken", auto_error=False)
query = APIKeyQuery(name="token", auto_error=False)


class User(BaseModel):
    username: str
    roles: Sequence[str]
    apikey: str


def current_api_token(
    apikey: Annotated[Optional[str], Depends(header)],
    apikey_from_cookie: Annotated[Optional[str], Depends(cookie)],
    apikey_from_query: Annotated[Optional[str], Depends(query)],
):
    if apikey_from_cookie:
        return apikey_from_cookie
    if apikey_from_query:
        return apikey_from_query
    if apikey:
        return apikey
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not authenticated")


def current_user(
    apikey: Annotated[str, Depends(current_api_token)],
):
    public_key = settings.jwt_public_key
    # TODO catch exceptions and raise 40x error
    data = jwt.decode(
        apikey,
        public_key,
        algorithms=["RS256"],
        # TODO verify more besides exp and public key
        # like aud, iss, nbf
    )
    return User(
        username=data["sub"],
        roles=data["roles"],
        apikey=apikey,
    )


CurrentUser = Annotated[User, Depends(current_user)]

# TODO add whoami endpoint which returns current user based on given token

# TODO allow super user to read jobs from all users
# alternativly allow super user to impersonate other users
# super user is use with 'super' role in roles claims

# TODO allow job to be readable by users who a member of a group
# 1. add endpoints to admin jobs groups
# 2. inside token of user add group memberships,
# use groups claims see https://www.iana.org/assignments/jwt/jwt.xhtml#claims

# TODO allow job to be readable by anonymous users aka without token
# Used for storing example jobs or scenarios
# Public job should not expire
# 1. add endpoints to admin jobs public readability
#    * endpoints should only be available to super user
