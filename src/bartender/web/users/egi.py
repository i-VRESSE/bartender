from typing import List, Literal, Optional

from httpx_oauth.clients.openid import OpenID

# Scopes taken from https://aai.egi.eu/federation/egi/form/new
BASE_SCOPES = ["openid", "email", "profile", "voperson_id", "eduperson_entitlement"]
CONFIGURATION_ENDPOINTS = {
    "production": "https://aai.egi.eu/auth/realms/egi/.well-known/openid-configuration",
    "development": "https://aai-dev.egi.eu/auth/realms/egi/.well-known/openid-configuration",
    "demo": "https://aai-demo.egi.eu/auth/realms/egi/.well-known/openid-configuration",
}


class EgiCheckinOAuth2(OpenID):
    """OAuth for EGI Checkin."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_scopes: Optional[List[str]] = BASE_SCOPES,
        environment: Literal["production", "development", "demo"] = "production",
    ):
        name = "EGI Checkin"
        if environment != "production":
            name += f" {environment}"
        super().__init__(
            client_id,
            client_secret,
            openid_configuration_endpoint=CONFIGURATION_ENDPOINTS[environment],
            name=name,
            base_scopes=base_scopes,
        )
