from __future__ import annotations

import pytest
from app.auth.keycloak import KeycloakTokenVerifier, StaticJWKClient
from fastapi import HTTPException

from .utils import build_token, default_settings, generate_rsa_material


def test_verify_valid_token_extracts_roles():
    private_pem, jwks = generate_rsa_material()
    verifier = KeycloakTokenVerifier(default_settings(), jwks_client=StaticJWKClient(jwks))

    token = build_token(private_pem)
    context = verifier.verify(token)

    assert context.subject == "user-123"
    assert context.email == "user@example.com"
    assert context.roles == ["org_admin", "super_admin"]


def test_verify_rejects_invalid_audience():
    private_pem, jwks = generate_rsa_material()
    verifier = KeycloakTokenVerifier(default_settings(), jwks_client=StaticJWKClient(jwks))

    token = build_token(private_pem, audience="wrong")
    with pytest.raises(HTTPException) as exc:
        verifier.verify(token)

    assert exc.value.status_code == 401
    assert "Invalid" in exc.value.detail


def test_verify_rejects_unknown_kid():
    private_pem, jwks = generate_rsa_material()
    verifier = KeycloakTokenVerifier(default_settings(), jwks_client=StaticJWKClient(jwks))

    token = build_token(private_pem, kid="unknown")
    with pytest.raises(HTTPException) as exc:
        verifier.verify(token)

    assert exc.value.status_code == 401
    assert "signing key" in exc.value.detail.lower()
