from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from ..config import Settings


class KeycloakOpenIDClient:
    """Performs lightweight OpenID discovery health checks against Keycloak."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check_health(self) -> None:
        discovery_url = f"{self._settings.keycloak_issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(discovery_url)
        if response.status_code >= 400:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Keycloak discovery endpoint is unavailable",
            )
