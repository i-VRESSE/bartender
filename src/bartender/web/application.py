from importlib import metadata

from fastapi import FastAPI
from fastapi.responses import UJSONResponse

from bartender.web.api.router import api_router
from bartender.web.lifespan import lifespan
from bartender.web.users.router import include_users_routes


def get_app() -> FastAPI:
    """Get FastAPI application.

    This is the main constructor of an application.

    Returns:
        application.
    """
    app = FastAPI(
        title="bartender",
        description="Job middleware for i-VRESSE",
        version=metadata.version("bartender"),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        default_response_class=UJSONResponse,
        lifespan=lifespan,
    )

    # Main router for the API.
    app.include_router(router=api_router, prefix="/api")

    include_users_routes(app)

    return app
