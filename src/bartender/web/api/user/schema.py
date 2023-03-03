from uuid import UUID

from pydantic import BaseModel


class OAuthAccountName(BaseModel):
    """DTO for social provider name (OAuth account from GithHub or Orcid) of a user."""

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

    class Config:
        orm_mode = True


class UserAsListItem(UserProfileInputDTO):
    """DTO for user in a list."""

    id: UUID
    is_active: bool
    is_superuser: bool
    is_verified: bool
