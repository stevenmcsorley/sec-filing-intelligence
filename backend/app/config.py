from __future__ import annotations

import os
from functools import lru_cache
from typing import TypedDict

from pydantic import AnyHttpUrl, BaseModel, Field, HttpUrl, ValidationError


class _KeycloakEnv(TypedDict):
    keycloak_server_url: str
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_audience: str


def _parse_algorithms() -> list[str]:
    raw = os.getenv("KEYCLOAK_ALGORITHMS", "RS256")
    return [alg.strip() for alg in raw.split(",") if alg.strip()]


class Settings(BaseModel):
    api_host: str = Field(default=os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default=int(os.getenv("API_PORT", "8000")))

    keycloak_server_url: AnyHttpUrl
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_audience: str
    keycloak_jwks_cache_ttl_seconds: int = Field(
        default=int(os.getenv("KEYCLOAK_JWKS_CACHE_TTL_SECONDS", "300"))
    )
    keycloak_algorithms: list[str] = Field(default_factory=_parse_algorithms)

    opa_url: HttpUrl | None = Field(default=os.getenv("OPA_URL"))

    @property
    def keycloak_issuer(self) -> str:
        base_url = str(self.keycloak_server_url).rstrip("/")
        return f"{base_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_issuer}/protocol/openid-connect/certs"


def _load_settings() -> Settings:
    environment = {
        "keycloak_server_url": os.getenv("KEYCLOAK_SERVER_URL"),
        "keycloak_realm": os.getenv("KEYCLOAK_REALM"),
        "keycloak_client_id": os.getenv("KEYCLOAK_CLIENT_ID"),
        "keycloak_audience": os.getenv("KEYCLOAK_AUDIENCE"),
    }

    missing = [key for key, value in environment.items() if value in (None, "")]
    if missing:
        raise RuntimeError(
            "Missing required Keycloak environment variables: " + ", ".join(missing)
        )

    assert environment["keycloak_server_url"] is not None
    assert environment["keycloak_realm"] is not None
    assert environment["keycloak_client_id"] is not None
    assert environment["keycloak_audience"] is not None

    typed_environment: _KeycloakEnv = {
        "keycloak_server_url": environment["keycloak_server_url"],
        "keycloak_realm": environment["keycloak_realm"],
        "keycloak_client_id": environment["keycloak_client_id"],
        "keycloak_audience": environment["keycloak_audience"],
    }

    try:
        return Settings.model_validate(typed_environment)
    except ValidationError as exc:  # pragma: no cover - pydantic already exercised in tests
        raise RuntimeError(f"Invalid settings detected: {exc}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _load_settings()
