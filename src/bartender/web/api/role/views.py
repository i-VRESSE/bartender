from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from bartender.db.dao.user_dao import get_user_db
from bartender.db.dependencies import get_db_session
from bartender.db.models.user import Role, User
from bartender.web.users.manager import current_super_user

router = APIRouter()


@router.get("/")
async def list_roles(
    session: AsyncSession = Depends(get_db_session),
    super_user: User = Depends(current_super_user),
) -> list[str]:
    """List available roles.

    Requires logged in user to be a super user.

    Args:
        session: DB session.
        super_user: Checks if current user is super.

    Returns:
        List of role names.
    """
    raw_jobs = await session.execute(select(Role))
    # TODO find nicer way to return just ids instead of looping
    return [role.id for role in raw_jobs.scalars().fetchall()]


@router.put("/{role_id}")
async def add_role(
    role_id: str,
    session: AsyncSession = Depends(get_db_session),
    super_user: User = Depends(current_super_user),
) -> str:
    """Add role.

    Requires logged in user to be a super user.

    Args:
        role_id: Name of role
        session: DB session.
        super_user: Checks if current user is super.

    Returns:
        Name of role
    """
    role = Role(id=role_id)
    session.add(role)
    await session.commit()
    return role_id


@router.delete("/{role_id}")
async def remove_role(
    role_id: str,
    session: AsyncSession = Depends(get_db_session),
    super_user: User = Depends(current_super_user),
) -> str:
    """Remove role.

    Requires logged in user to be a super user.

    Args:
        role_id: Name of role
        session: DB session.
        super_user: Checks if current user is super.

    Returns:
        Name of role
    """
    role = Role(id=role_id)
    await session.delete(role)
    await session.commit()
    return role_id


@router.put("/{role_id}/{user_id}")
async def grant_role_to_user(
    role_id: str,
    user_id: str,
    super_user: User = Depends(current_super_user),
    user_db: SQLAlchemyUserDatabase[User, UUID] = Depends(get_user_db),
) -> list[Role]:
    """Grant role to user.

    Args:
        role_id: Role id
        user_id: User id
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
    user.roles.append(Role(id=role_id))
    await user_db.session.commit()
    await user_db.session.refresh(user)
    return user.roles


@router.delete("/{role_id}/{user_id}")
async def revoke_role_from_user(
    role_id: str,
    user_id: str,
    super_user: User = Depends(current_super_user),
    user_db: SQLAlchemyUserDatabase[User, UUID] = Depends(get_user_db),
) -> list[Role]:
    """Revoke role from user.

    Args:
        role_id: Role id
        user_id: User id
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
    user.roles.remove(Role(id=role_id))
    await user_db.session.commit()
    await user_db.session.refresh(user)
    return user.roles


# TODO test all methods here
# TODO add roles to jwt token
# TODO list roles in /users/me + /api/users/profile
# TODO add allowed roles to application config
# while reading config should make sure roles are present in db
# eg. ['haddock3:easy', 'haddock3:expert', 'haddock3:guru']
# TODO add required roles to application config
# eg. ['haddock:'] -> any haddock:* role will suffice
# eg. [] or None -> no role required
