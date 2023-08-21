from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Sequence

from jose import jwk, jwt
from jose.backends.base import Key
from pydantic import BaseModel


class User(BaseModel):
    """User model."""

    username: str
    roles: Sequence[str] = []
    apikey: str


class JwtDecoder:
    """JWT decoder.

    Args:
        key: The key to use for decoding the JWT token.

    """

    def __init__(self, key: Key):
        self.key = key

    def __call__(self, apikey: str) -> User:
        """Decodes a JWT token and returns a User object.

        Raises an JOSE exception if the token is invalid.

        Args:
            apikey (str): The JWT token to decode.

        Returns:
            User: A User object.
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
            self.key,
            algorithms=["RS256"],
            # TODO verify more besides exp and public key
            # like aud, iss, nbf
            options=options,
            # TODO check issuer is allowed with settings.issuer_whitelist
        )
        return User(
            username=data["sub"],
            roles=data["roles"] if "roles" in data else [],
            apikey=apikey,
            # TODO store issuer in db so we can see from where job was submitted?
        )

    @classmethod
    def from_file(cls, public_key: Path) -> "JwtDecoder":
        """Create a JwtDecoder from a public key file.

        Args:
            public_key: Path to the public key file.

        Returns:
            A JwtDecoder object.
        """
        public_key_body = public_key.read_bytes()
        return cls.from_bytes(public_key_body)

    @classmethod
    def from_bytes(cls, public_key: bytes) -> "JwtDecoder":
        """Create a JwtDecoder from a public key.

        Args:
            public_key: The public key.

        Returns:
            A JwtDecoder object.
        """
        return cls(jwk.construct(public_key, "RS256"))


def generate_token_subcommand(  # noqa: WPS211 -- too many arguments
    private_key: Path,
    username: str,
    roles: list[str],
    lifetime: int,
    issuer: str,
    oformat: Literal["header", "plain"] = "plain",
) -> None:
    """Generate a JSON Web Token (JWT) with the given parameters.

    Args:
        private_key: Path to the private key file.
        username: The username to include in the token.
        roles: A list of roles to include in the token.
        lifetime: The lifetime of the token in minutes.
        issuer: The issuer of the token.
        oformat: The format of the token output. Can be "header" or "plain".

    Returns:
        None
    """
    private_key_body = Path(private_key).read_bytes()
    expire = datetime.utcnow() + timedelta(minutes=lifetime)
    token = generate_token(
        private_key=private_key_body,
        username=username,
        roles=roles,
        expire=expire,
        issuer=issuer,
    )
    if oformat == "header":
        print(f"Authorization: Bearer {token}")  # noqa: WPS421 -- user feedback
    else:
        print(token)  # noqa: WPS421 -- user feedback


def generate_token(
    private_key: bytes,
    username: str,
    roles: list[str],
    expire: datetime,
    issuer: str,
) -> str:
    """Generate a JSON Web Token (JWT).

    Args:
        private_key: The private key to use for signing the token.
        username: The username to include in the token.
        roles: A list of roles to include in the token.
        expire: When token expires.
        issuer: The issuer of the token.

    Returns:
        The generated token.
    """
    # TODO use scope to allow different actions
    # no scope could only be used to list applications and check health
    # scope:read could be used to read your own job
    # scope:write could be used to allow submission/deletion jobs

    # TODO allow super user to read jobs from all users
    # by allowing super user to impersonate other users
    # with act claim
    # see https://www.rfc-editor.org/rfc/rfc8693.html#name-act-actor-claim
    # https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-token-claims
    # https://www.iana.org/assignments/jwt/jwt.xhtml#claims
    # alternativly a super user could also have 'super' role in roles claims

    # TODO allow job to be readable by users who is member of a group
    # use groups claims see https://www.iana.org/assignments/jwt/jwt.xhtml#claims
    # add group column job table, so on submission we store which group can read
    # the job. Add endpoints to add/remove group to/from existing job

    # TODO allow job to be readable by anonymous users aka without token
    # Used for storing example jobs or scenarios
    # User should have super role.
    # Add public boolena column to job table
    # Add endpoints to make job public or private
    # Public job should not expire
    payload = {
        "sub": username,
        "exp": expire,
        "roles": roles,
        "iss": issuer,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")
