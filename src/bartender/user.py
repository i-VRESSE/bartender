from typing import Sequence

from jose import jwt
from jose.backends.base import Key
from pydantic import BaseModel


class User(BaseModel):
    """User model."""

    username: str
    roles: Sequence[str] = []
    apikey: str


def token2user(apikey: str, public_key: Key) -> User:
    """Decodes a JWT token and returns a User object.

    Args:
        apikey (str): The JWT token to decode.
        public_key (Key): The public key to use for decoding the token.

    Returns:
        User: A User object representing the decoded token.
    """
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
        # TODO check issuer is allowed with settings.issuer_whitelist
    )
    return User(
        username=data["sub"],
        roles=data["roles"],
        apikey=apikey,
        # TODO store issuer in db so we can see from where job was submitted?
    )
