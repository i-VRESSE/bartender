import uuid

from fastapi_users import schemas

# From app/schemas.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


class UserRead(schemas.BaseUser[uuid.UUID]):
    """DTO for read user."""


class UserCreate(schemas.BaseUserCreate):
    """DTO to create user."""


class UserUpdate(schemas.BaseUserUpdate):
    """DTO to update user."""
