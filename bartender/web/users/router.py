from fastapi import FastAPI

from bartender.settings import settings
from bartender.web.users.manager import auth_backend, fastapi_users, github_oauth_client
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
    # Routes require sending mail, removed for now
    # as we prefer social login over local account.
    # See https://fastapi-users.github.io/fastapi-users/10.1/configuration/full-example/
    # to add get_reset_password_router + get_verify_router back

    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
    if github_oauth_client is not None:
        # From app/app.py at
        # https://fastapi-users.github.io/fastapi-users/10.1/configuration/oauth

        app.include_router(
            fastapi_users.get_oauth_router(
                github_oauth_client,
                auth_backend,
                settings.secret,
                associate_by_email=True,
            ),
            prefix="/auth/github",
            tags=["auth"],
        )
        app.include_router(
            fastapi_users.get_oauth_associate_router(
                github_oauth_client,
                UserRead,
                settings.secret,
            ),
            prefix="/auth/associate/github",
            tags=["auth"],
        )
        # TODO An access token given in the callback response.
        # The Swagger UI does not allow to authorize with a access token.
        # It would be nice to add JWT bearer security scheme to each protected route
        # see https://spec.openapis.org/oas/v3.1.0#jwt-bearer-sample
        # do this without breaking the username/password authorize in Swagger UI
