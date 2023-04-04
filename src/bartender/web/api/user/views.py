from fastapi import APIRouter

from bartender.db.dao.user_dao import CurrentUserDatabase
from bartender.db.models.user import User
from bartender.web.api.user.schema import UserAsListItem, UserProfileInputDTO
from bartender.web.users.manager import CurrentSuperUser, CurrentUser

router = APIRouter()

# From app/app.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


@router.get("/profile", response_model=UserProfileInputDTO)
async def profile(
    user: CurrentUser,
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
    super_user: CurrentSuperUser,
    user_db: CurrentUserDatabase,
    limit: int = 50,
    offset: int = 0,
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
