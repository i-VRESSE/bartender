import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status


@pytest.mark.anyio
async def test_profile(client: AsyncClient, fastapi_app: FastAPI) -> None:
    """
    Checks the profile endpoint.

    :param client: client for the app.
    :param fastapi_app: current FastAPI application.
    """
    new_user = {"email": "me@example.com", "password": "mysupersecretpassword"}
    await client.post(fastapi_app.url_path_for("register:register"), json=new_user)
    login_response = await client.post(
        fastapi_app.url_path_for("auth:local.login"),
        data={
            "grant_type": "password",
            "username": new_user["email"],
            "password": new_user["password"],
        },
    )
    token = login_response.json()["access_token"]

    url = fastapi_app.url_path_for(
        "profile",
    )

    response = await client.get(url, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == status.HTTP_200_OK

    expected = {
        "email": "me@example.com",
        "oauth_accounts": [],
    }
    assert response.json() == expected
