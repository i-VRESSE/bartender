from fastapi import FastAPI

from bartender.web.users.manager import auth_backend, fastapi_users
from bartender.web.users.schema import UserCreate, UserRead, UserUpdate

# From app/app.py at
# https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/


def include_users_routes(app: FastAPI) -> None:
    """Register fastapi_users routes.

    :param app: FastAPI app
    """
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/jwt",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
