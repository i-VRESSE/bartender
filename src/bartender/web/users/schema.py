import uuid
from typing import Any

from fastapi_users import schemas
from pydantic import validator

# From app/schemas.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


class UserRead(schemas.BaseUser[uuid.UUID]):
    """DTO for read user."""

    roles: list[str]

    @validator("roles", pre=True)
    def _handle_roles_none(cls, value: Any) -> Any:  # noqa: N805 is class method
        if value is None:
            return []
        return value


class UserCreate(schemas.BaseUserCreate):
    """DTO to create user."""


class UserUpdate(schemas.BaseUserUpdate):
    """DTO to update user."""
