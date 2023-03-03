from fastapi import APIRouter, Depends

from bartender.db.dao.user_dao import UserDatabase, get_user_db
from bartender.db.models.user import User
from bartender.web.api.user.schema import UserAsListItem, UserProfileInputDTO
from bartender.web.users.manager import current_active_user, current_super_user

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


@router.get(
    "/",
    response_model=list[UserAsListItem],
)
async def list_users(
    limit: int = 50,
    offset: int = 0,
    super_user: User = Depends(current_super_user),
    user_db: UserDatabase = Depends(get_user_db),
) -> list[User]:
    """List of users.

    Requires super user powers.

    Args:
        limit: Number of users to return. Defaults to 50.
        offset: Offset. Defaults to 0.
        super_user: Check if current user is super.
        user_db: User db.

    Returns:
        List of users.
    """
    return await user_db.list(limit, offset)
