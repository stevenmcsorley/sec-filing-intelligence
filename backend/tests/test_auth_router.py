from __future__ import annotations

import pytest
from app.auth.dependencies import (
    _build_openid_client,
    _build_token_verifier,
    get_openid_client,
    get_token_verifier,
)
from app.auth.keycloak import KeycloakTokenVerifier, StaticJWKClient
from app.config import get_settings
from app.main import app
from fastapi.testclient import TestClient

from .utils import build_token, default_settings, generate_rsa_material


@pytest.fixture(autouse=True)
def configure_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_SERVER_URL", "http://localhost:8080")
    monkeypatch.setenv("KEYCLOAK_REALM", "sec-intel")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "backend")
    monkeypatch.setenv("KEYCLOAK_AUDIENCE", "backend")
    monkeypatch.setenv("KEYCLOAK_JWKS_CACHE_TTL_SECONDS", "300")

    get_settings.cache_clear()
    _build_token_verifier.cache_clear()
    _build_openid_client.cache_clear()
    yield
    get_settings.cache_clear()
    _build_token_verifier.cache_clear()
    _build_openid_client.cache_clear()


class _StubOpenIDClient:
    async def check_health(self) -> None:  # pragma: no cover - behaviour verified via call
        return None


def test_auth_endpoints_return_context():
    private_pem, jwks = generate_rsa_material()
    verifier = KeycloakTokenVerifier(default_settings(), jwks_client=StaticJWKClient(jwks))

    def override_verifier():
        return verifier

    def override_openid():
        return _StubOpenIDClient()

    app.dependency_overrides[get_token_verifier] = override_verifier
    app.dependency_overrides[get_openid_client] = override_openid

    token = build_token(private_pem)
    client = TestClient(app)

    health_response = client.get("/auth/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    me_response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    payload = me_response.json()
    assert payload["sub"] == "user-123"
    assert payload["roles"] == ["org_admin", "super_admin"]

    missing_response = client.get("/auth/me")
    assert missing_response.status_code == 401

    app.dependency_overrides.clear()
