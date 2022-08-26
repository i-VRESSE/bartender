from fastapi.routing import APIRouter

from bartender.web.api import job, monitoring

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(job.router, prefix="/job", tags=["job"])
