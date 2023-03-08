from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from starlette import status

from bartender.config import get_roles
from bartender.db.dao.user_dao import UserDatabase, get_user_db
from bartender.db.models.user import User
from bartender.web.users.manager import current_super_user

router = APIRouter()


@router.get("/", response_model=list[str])
async def list_roles(
    roles: set[str] = Depends(get_roles),
    super_user: User = Depends(current_super_user),
) -> set[str]:
    """List available roles.

    Requires logged in user to be a super user.

    Args:
        roles: Roles from config.
        super_user: Checks if current user is super.

    Returns:
        List of role names.
    """
    return roles


@router.put("/{role_id}/{user_id}")
async def grant_role_to_user(
    role_id: str,
    user_id: str,
    roles: set[str] = Depends(get_roles),
    super_user: User = Depends(current_super_user),
    user_db: UserDatabase = Depends(get_user_db),
) -> list[str]:
    """Grant role to user.

    Requires super user powers.

    Args:
        role_id: Role id
        user_id: User id
        roles: Set of allowed roles
        super_user: Check if current user is super.
        user_db: User db.

    Raises:
        HTTPException: When user is not found

    Returns:
        Roles granted to user.
    """
    user = await user_db.get(UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if role_id not in roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    await user_db.grant_role(user, role_id)
    return user.roles


@router.delete("/{role_id}/{user_id}")
async def revoke_role_from_user(
    role_id: str,
    user_id: str,
    roles: set[str] = Depends(get_roles),
    super_user: User = Depends(current_super_user),
    user_db: UserDatabase = Depends(get_user_db),
) -> list[str]:
    """Revoke role from user.

    Requires super user powers.

    Args:
        role_id: Role id
        user_id: User id
        roles: Set of allowed roles
        super_user: Check if current user is super.
        user_db: User db.

    Raises:
        HTTPException: When user is not found

    Returns:
        Roles granted to user.
    """
    user = await user_db.get(UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if role_id not in roles or role_id not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    await user_db.revoke_role(user, role_id)
    return user.roles


# TODO test all methods here
