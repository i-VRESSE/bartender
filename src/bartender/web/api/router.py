from fastapi.routing import APIRouter

from bartender.web.api import applications, job, monitoring
from bartender.web.users import CurrentUser, User

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(job.router, prefix="/job", tags=["job"])
api_router.include_router(
    applications.router,
    prefix="/application",
    tags=["application"],
)


@api_router.get("/whoami", tags=["user"])
def whoami(user: CurrentUser) -> User:
    """Get current user based on API key.

    Args:
        user: Current user.

    Returns:
        Current logged in user.
    """
    return user
