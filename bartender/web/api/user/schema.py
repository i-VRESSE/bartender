from pydantic import BaseModel


class OAuthAccountName(BaseModel):
    """DTO for social provider name (OAuth account from GithHub or Orcid) of a user."""

    oauth_name: str

    class Config:
        orm_mode = True


class UserProfileInputDTO(BaseModel):
    """DTO for profile of current user model."""

    email: str
    oauth_accounts: list[OAuthAccountName]

    class Config:
        orm_mode = True
