from fastapi import APIRouter, Depends

from bartender.db.models.user import User
from bartender.web.api.user.schema import UserProfileInputDTO
from bartender.web.users.manager import current_active_user

router = APIRouter()

# From app/app.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


@router.get("/profile", response_model=UserProfileInputDTO)
async def profile(
    user: User = Depends(current_active_user),
) -> User:
    """
    Retrieve profile of currently logged in user.

    Args:
        user: Current active user.

    Returns:
        user profile.
    """
    return user
