from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..config import Settings, get_settings
from .keycloak import KeycloakTokenVerifier
from .models import TokenContext
from .openid import KeycloakOpenIDClient

http_bearer = HTTPBearer(auto_error=False)


SettingsDep = Annotated[Settings, Depends(get_settings)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)]


@lru_cache(maxsize=1)
def _build_token_verifier(
    server_url: str,
    realm: str,
    audience: str,
    jwks_url: str,
    algorithms: tuple[str, ...],
) -> KeycloakTokenVerifier:
    settings = get_settings()
    return KeycloakTokenVerifier.from_settings(settings)


def get_token_verifier(settings: SettingsDep) -> KeycloakTokenVerifier:
    return _build_token_verifier(
        settings.keycloak_server_url,
        settings.keycloak_realm,
        settings.keycloak_audience,
        settings.keycloak_jwks_url,
        tuple(settings.keycloak_algorithms),
    )


def get_current_token(
    credentials: CredentialsDep,
    verifier: Annotated[KeycloakTokenVerifier, Depends(get_token_verifier)],
) -> TokenContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return verifier.verify(credentials.credentials)


@lru_cache(maxsize=1)
def _build_openid_client(server_url: str, realm: str) -> KeycloakOpenIDClient:
    return KeycloakOpenIDClient(get_settings())


def get_openid_client(settings: SettingsDep) -> KeycloakOpenIDClient:
    return _build_openid_client(settings.keycloak_server_url, settings.keycloak_realm)
