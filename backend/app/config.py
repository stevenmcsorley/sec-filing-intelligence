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


def _parse_company_ciks() -> list[str]:
    raw = os.getenv("EDGAR_COMPANY_CIKS", "")
    return [token.strip() for token in raw.split(",") if token.strip()]


class Settings(BaseModel):
    api_host: str = Field(default=os.getenv("API_HOST", "0.0.0.0"))
    api_port: int = Field(default=int(os.getenv("API_PORT", "8000")))

    database_url: str = Field(
        default=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://filings:filings@postgres:5432/filings",
        )
    )
    database_echo: bool = Field(
        default=os.getenv("DATABASE_ECHO", "false").lower() == "true"
    )

    keycloak_server_url: AnyHttpUrl
    keycloak_realm: str
    keycloak_client_id: str
    keycloak_audience: str
    keycloak_jwks_cache_ttl_seconds: int = Field(
        default=int(os.getenv("KEYCLOAK_JWKS_CACHE_TTL_SECONDS", "300"))
    )
    keycloak_algorithms: list[str] = Field(default_factory=_parse_algorithms)

    opa_url: HttpUrl | None = Field(default=os.getenv("OPA_URL"))

    redis_url: str = Field(default=os.getenv("REDIS_URL", "redis://redis:6379/0"))

    edgar_polling_enabled: bool = Field(
        default=os.getenv("EDGAR_POLLING_ENABLED", "true").lower() == "true"
    )
    edgar_user_agent: str = Field(
        default=os.getenv(
            "EDGAR_USER_AGENT",
            "Mozilla/5.0 (compatible; sec-filing-intel/0.1; support@sec-intel.local)",
        )
    )
    edgar_global_feed_url: AnyHttpUrl = Field(
        default=os.getenv(
            "EDGAR_GLOBAL_FEED_URL",
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&count=100&output=atom",
        )
    )
    edgar_company_feed_base_url: AnyHttpUrl = Field(
        default=os.getenv(
            "EDGAR_COMPANY_FEED_BASE_URL",
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=",
        )
    )
    edgar_global_poll_interval_seconds: int = Field(
        default=int(os.getenv("EDGAR_GLOBAL_POLL_INTERVAL_SECONDS", "60"))
    )
    edgar_company_poll_interval_seconds: int = Field(
        default=int(os.getenv("EDGAR_COMPANY_POLL_INTERVAL_SECONDS", "300"))
    )
    edgar_company_ciks: list[str] = Field(default_factory=_parse_company_ciks)
    edgar_download_queue_name: str = Field(
        default=os.getenv("EDGAR_DOWNLOAD_QUEUE_NAME", "sec:ingestion:download")
    )
    edgar_seen_accessions_key: str = Field(
        default=os.getenv("EDGAR_SEEN_ACCESSIONS_KEY", "sec:ingestion:seen-accessions")
    )

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
