from typing import Dict

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

@pytest.mark.anyio
async def test_list_roles_given_no_roles_in_config(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
):
    url = fastapi_app.url_path_for(
        "list_roles",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    expected = []
    assert response.json() == expected