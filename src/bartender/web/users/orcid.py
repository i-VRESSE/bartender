from typing import Any, Dict, List, Optional, Tuple, cast

from httpx_oauth.errors import GetIdEmailError
from httpx_oauth.oauth2 import BaseOAuth2
from starlette import status

AUTHORIZE_ENDPOINT = "https://{domain}/oauth/authorize"
ACCESS_TOKEN_ENDPOINT = "https://{domain}/oauth/token"  # noqa: S105 -- not a password
BASE_SCOPES = ["openid"]
PROFILE_ENDPOINT = "https://{domain}/oauth/userinfo"
EMAILS_ENDPOINT = "https://pub.{domain}/v3.0/{id}/email"


class OrcidOAuth2(BaseOAuth2[Dict[str, Any]]):
    """OAuth for Orcid."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_scopes: Optional[List[str]] = BASE_SCOPES,
        is_sandbox: bool = False,
    ):
        self.domain = "sandbox.orcid.org" if is_sandbox else "orcid.org"
        super().__init__(
            client_id,
            client_secret,
            AUTHORIZE_ENDPOINT.format(domain=self.domain),
            ACCESS_TOKEN_ENDPOINT.format(domain=self.domain),
            name=self.domain,
            base_scopes=base_scopes,
        )

    async def get_id_email(self, token: str) -> Tuple[str, str]:
        """Retrieve account id and email.

        Args:
            token: Orcid token

        Returns:
            Tuple with account id and email
        """
        orcid_id = await self._get_orcid_id(token)
        email = await self._get_email(orcid_id)
        return (orcid_id, email)

    async def _get_orcid_id(self, token: str) -> str:
        async with self.get_httpx_client() as client:
            headers = self.request_headers.copy()
            headers["Authorization"] = f"Bearer {token}"
            profile_response = await client.get(
                PROFILE_ENDPOINT.format(domain=self.domain),
                headers=headers,
            )

            if profile_response.status_code >= status.HTTP_400_BAD_REQUEST:
                raise GetIdEmailError(profile_response.json())

            profile_data = cast(Dict[str, str], profile_response.json())
            return profile_data["sub"]

    async def _get_email(self, orcid_id: str) -> str:
        async with self.get_httpx_client() as client:
            email_url = EMAILS_ENDPOINT.format(domain=self.domain, id=orcid_id)
            email_response = await client.get(email_url, headers=self.request_headers)

            if email_response.status_code >= status.HTTP_400_BAD_REQUEST:
                raise GetIdEmailError(email_response.json())

            email_data = cast(Dict[str, Any], email_response.json())
            if "email" in email_data and email_data["email"]:
                return cast(str, email_data["email"][0]["email"])
            return f"{orcid_id}@{self.domain}"
