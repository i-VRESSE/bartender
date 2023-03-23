from fastapi.routing import APIRouter

from bartender.web.api import applications, job, monitoring, role, user

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(job.router, prefix="/job", tags=["job"])
api_router.include_router(
    applications.router,
    prefix="/application",
    tags=["application"],
)
api_router.include_router(user.router, prefix="/users", tags=["users"])
api_router.include_router(role.router, prefix="/roles", tags=["roles"])
