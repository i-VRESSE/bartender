from typing import Any
from uuid import UUID

from pydantic import BaseModel, validator


class OAuthAccountName(BaseModel):
    """DTO for social providers name of a user."""

    oauth_name: str
    account_id: str
    account_email: str

    class Config:
        orm_mode = True


class UserProfileInputDTO(BaseModel):
    """DTO for profile of current user model."""

    email: str
    oauth_accounts: list[OAuthAccountName]
    roles: list[str]

    @validator("roles", pre=True)
    def _handle_roles_none(cls, value: Any) -> Any:  # noqa: N805 is class method
        if value is None:
            return []
        return value

    class Config:
        orm_mode = True


class UserAsListItem(UserProfileInputDTO):
    """DTO for user in a list."""

    id: UUID
    is_active: bool
    is_superuser: bool
    is_verified: bool
