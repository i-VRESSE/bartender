from typing import Dict

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from tests.conftest import MockUser


@pytest.mark.anyio
async def test_profile(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
) -> None:
    """Checks the profile endpoint.

    Args:
        client: client for the app.
        fastapi_app: current FastAPI application.
    """
    url = fastapi_app.url_path_for(
        "profile",
    )

    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    expected = {
        "email": "me@example.com",
        "oauth_accounts": [],
        "roles": [],
    }
    assert response.json() == expected


@pytest.mark.anyio
async def test_list_users(
    client: AsyncClient,
    app_with_roles: FastAPI,
    current_user_is_super: None,
    current_user_with_role: None,
    current_user_model: MockUser,
    auth_headers: Dict[str, str],
) -> None:
    url = app_with_roles.url_path_for(
        "list_users",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    expected = [
        {
            "email": current_user_model["email"],
            "id": current_user_model["id"],
            "oauth_accounts": [],
            "roles": ["role1"],
            "is_active": True,
            "is_superuser": True,
            "is_verified": False,
        },
    ]
    assert response.json() == expected
