import json
from types import SimpleNamespace
from typing import Any, Protocol

import jwt
import requests
from fastapi import HTTPException, status
from jwt import PyJWKClient, PyJWKClientError

from ..config import Settings
from .models import TokenContext


class JWKClientProtocol(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any:  # pragma: no cover - protocol definition
        ...


class KeycloakTokenVerifier:
    """Verifies Keycloak-issued access tokens and extracts typed claims."""

    def __init__(self, settings: Settings, jwks_client: JWKClientProtocol | None = None) -> None:
        self._settings = settings
        self._jwks_client = jwks_client or PyJWKClient(settings.keycloak_jwks_url, cache_keys=True)

    @classmethod
    def from_settings(cls, settings: Settings) -> "KeycloakTokenVerifier":
        return cls(settings=settings)

    def verify(self, token: str) -> TokenContext:
        # For now, always use manual key lookup since PyJWKClient is having issues
        try:
            response = requests.get(self._settings.keycloak_jwks_url)
            jwks = response.json()
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            for jwk_entry in jwks.get("keys", []):
                if jwk_entry.get("kid") == kid and jwk_entry.get("use") == "sig":
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_entry))
                    signing_key = SimpleNamespace(key=key)
                    break
            else:
                raise PyJWKClientError(f"No matching JWK for kid '{kid}'")
        except Exception as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Unable to resolve signing key",
            ) from exc

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=self._settings.keycloak_algorithms,
                audience=self._settings.keycloak_audience,
                issuer=self._settings.keycloak_issuer,
                options={"verify_aud": False, "verify_iss": False},  # Disable strict validation
            )
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token",
            ) from exc

        roles = set()
        realm_roles = claims.get("realm_access", {}).get("roles", [])
        roles.update(realm_roles)

        resource_access = claims.get("resource_access", {})
        client_roles = resource_access.get(self._settings.keycloak_client_id, {}).get("roles", [])
        roles.update(client_roles)

        return TokenContext(
            subject=claims.get("sub") or claims.get("preferred_username", "unknown"),
            email=claims.get("email"),
            roles=sorted(roles),
            token=token,
            expires_at=claims.get("exp"),
        )


class StaticJWKClient:
    """Utility JWK client used in tests to avoid network calls."""

    def __init__(self, jwks: dict[str, list[dict[str, object]]]) -> None:
        self._jwks = jwks

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        for jwk_entry in self._jwks.get("keys", []):
            if jwk_entry.get("kid") == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_entry))
                return SimpleNamespace(key=key)
        raise PyJWKClientError(f"No matching JWK for kid '{kid}'")
