from fastapi import APIRouter
from sqlalchemy import text

from bartender.db.dependencies import CurrentSession

router = APIRouter()


@router.get("/health")
async def health_check(
    session: CurrentSession,
) -> None:
    """
    Checks the health of a project.

    It returns 200 if the project is healthy.
    """
    # TODO check
    # 1. Database connection is live
    await session.execute(text("SELECT 1"))
    # 2. Schedulers and filesystems of job destinations are working.
