from typing import Dict

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status


@pytest.mark.anyio
async def test_profile(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
) -> None:
    """
    Checks the profile endpoint.

    :param client: client for the app.
    :param fastapi_app: current FastAPI application.
    """
    url = fastapi_app.url_path_for(
        "profile",
    )

    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    expected = {
        "email": "me@example.com",
        "oauth_accounts": [],
    }
    assert response.json() == expected
