from __future__ import annotations

import json
import time

import jwt
from app.config import Settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_material(kid: str = "test-key") -> tuple[bytes, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.setdefault("kid", kid)
    public_jwk.setdefault("use", "sig")
    public_jwk.setdefault("alg", "RS256")
    return private_pem, {"keys": [public_jwk]}


def default_settings() -> Settings:
    return Settings(
        keycloak_server_url="http://localhost:8080",
        keycloak_realm="sec-intel",
        keycloak_client_id="backend",
        keycloak_audience="backend",
    )


def build_token(
    private_pem: bytes,
    *,
    kid: str = "test-key",
    audience: str | None = None,
    roles: list[str] | None = None,
    expires_in: int = 3600,
    subject: str = "user-123",
    email: str = "user@example.com",
) -> str:
    settings = default_settings()
    now = int(time.time())
    claims = {
        "sub": subject,
        "email": email,
        "iss": settings.keycloak_issuer,
        "aud": audience or settings.keycloak_audience,
        "iat": now,
        "exp": now + expires_in,
        "realm_access": {"roles": ["super_admin"]},
        "resource_access": {
            settings.keycloak_client_id: {"roles": roles or ["org_admin"]}
        },
    }
    return jwt.encode(claims, private_pem, algorithm="RS256", headers={"kid": kid})
