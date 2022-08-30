from pydantic import BaseModel


class UserProfileInputDTO(BaseModel):
    """DTO for profile of current user model."""

    email: str
