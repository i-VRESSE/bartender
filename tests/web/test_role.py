from typing import Dict

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status


@pytest.mark.anyio
async def test_list_roles(
    client: AsyncClient,
    app_with_roles: FastAPI,
    current_user_is_super: None,
    auth_headers: Dict[str, str],
) -> None:
    url = app_with_roles.url_path_for(
        "list_roles",
    )
    response = await client.get(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK

    expected = ["role1"]
    assert response.json() == expected


@pytest.mark.anyio
async def test_assign_role_to_user(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_with_role: None,
) -> None:
    # assign_role_to_user is exercised in current_user_with_role fixture.

    url = fastapi_app.url_path_for(
        "profile",
    )
    response = await client.get(url, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    expected = ["role1"]
    assert response.json()["roles"] == expected


@pytest.mark.anyio
async def test_assign_role_to_user_given_bad_user(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_is_super: None,
) -> None:
    # uuid taken from https://en.wikipedia.org/wiki/Universally_unique_identifier
    bad_user_id = "123e4567-e89b-12d3-a456-426614174000"
    url = fastapi_app.url_path_for(
        "assign_role_to_user",
        role_id="role1",
        user_id=bad_user_id,
    )
    response = await client.put(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User not found" in response.text


@pytest.mark.anyio
async def test_assign_role_to_user_given_bad_role(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_is_super: None,
    current_user_id: str,
) -> None:
    url = fastapi_app.url_path_for(
        "assign_role_to_user",
        role_id="badrole1",
        user_id=current_user_id,
    )
    response = await client.put(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Role not found" in response.text


@pytest.mark.anyio
async def test_unassign_role_from_user_given_role1_has_been_assigned(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_with_role: None,
    current_user_id: str,
) -> None:
    url = fastapi_app.url_path_for(
        "unassign_role_from_user",
        role_id="role1",
        user_id=current_user_id,
    )
    response = await client.delete(url, headers=auth_headers)

    assert response.status_code == status.HTTP_200_OK
    assert not len(response.json())

    url = fastapi_app.url_path_for("profile")
    profile_response = await client.get(url, headers=auth_headers)
    assert profile_response.status_code == status.HTTP_200_OK
    assert not profile_response.json()["roles"]


@pytest.mark.anyio
async def test_unassign_role_from_user_given_bad_user(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_is_super: None,
) -> None:
    # uuid taken from https://en.wikipedia.org/wiki/Universally_unique_identifier
    bad_user_id = "123e4567-e89b-12d3-a456-426614174000"
    url = fastapi_app.url_path_for(
        "unassign_role_from_user",
        role_id="role1",
        user_id=bad_user_id,
    )
    response = await client.delete(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User not found" in response.text


@pytest.mark.anyio
async def test_unassign_role_from_user_given_bad_role(
    client: AsyncClient,
    fastapi_app: FastAPI,
    auth_headers: Dict[str, str],
    current_user_is_super: None,
    current_user_id: str,
) -> None:
    url = fastapi_app.url_path_for(
        "unassign_role_from_user",
        role_id="badrole1",
        user_id=current_user_id,
    )
    response = await client.delete(url, headers=auth_headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Role not found" in response.text
