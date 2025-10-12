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


def _optional_int_env(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - configuration validation
        raise ValueError(f"Invalid integer for {name}: {raw}") from exc


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

    downloader_enabled: bool = Field(
        default=os.getenv("DOWNLOADER_ENABLED", "true").lower() == "true"
    )
    downloader_concurrency: int = Field(
        default=int(os.getenv("DOWNLOADER_CONCURRENCY", "2"))
    )
    downloader_max_retries: int = Field(
        default=int(os.getenv("DOWNLOADER_MAX_RETRIES", "3"))
    )
    downloader_backoff_seconds: float = Field(
        default=float(os.getenv("DOWNLOADER_BACKOFF_SECONDS", "1.5"))
    )
    downloader_request_timeout: float = Field(
        default=float(os.getenv("DOWNLOADER_REQUEST_TIMEOUT", "30"))
    )
    downloader_visibility_timeout_seconds: int = Field(
        default=int(os.getenv("DOWNLOADER_VISIBILITY_TIMEOUT_SECONDS", "60"))
    )
    downloader_requeue_batch_size: int = Field(
        default=int(os.getenv("DOWNLOADER_REQUEUE_BATCH_SIZE", "100"))
    )

    chunk_queue_name: str = Field(
        default=os.getenv("CHUNK_QUEUE_NAME", "sec:groq:chunk")
    )
    chunk_queue_visibility_timeout_seconds: int = Field(
        default=int(os.getenv("CHUNK_QUEUE_VISIBILITY_TIMEOUT_SECONDS", "600"))
    )
    chunk_queue_requeue_batch_size: int = Field(
        default=int(os.getenv("CHUNK_QUEUE_REQUEUE_BATCH_SIZE", "200"))
    )
    chunk_queue_pause_threshold: int = Field(
        default=int(os.getenv("CHUNK_QUEUE_PAUSE_THRESHOLD", "1000"))
    )
    chunk_queue_resume_threshold: int = Field(
        default=int(os.getenv("CHUNK_QUEUE_RESUME_THRESHOLD", "750"))
    )
    chunk_backpressure_check_interval_seconds: float = Field(
        default=float(os.getenv("CHUNK_BACKPRESSURE_CHECK_INTERVAL_SECONDS", "1.0"))
    )
    chunker_max_tokens_per_chunk: int = Field(
        default=int(os.getenv("CHUNKER_MAX_TOKENS_PER_CHUNK", "800"))
    )
    chunker_min_tokens_per_chunk: int = Field(
        default=int(os.getenv("CHUNKER_MIN_TOKENS_PER_CHUNK", "200"))
    )
    chunker_paragraph_overlap: int = Field(
        default=int(os.getenv("CHUNKER_PARAGRAPH_OVERLAP", "1"))
    )

    groq_api_key: str | None = Field(default=os.getenv("GROQ_API_KEY"))
    groq_api_url: AnyHttpUrl = Field(
        default=os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1")
    )
    groq_budget_cooldown_seconds: int = Field(
        default=int(os.getenv("GROQ_BUDGET_COOLDOWN_SECONDS", "60"))
    )
    summarizer_enabled: bool = Field(
        default=os.getenv("SUMMARIZER_ENABLED", "true").lower() == "true"
    )
    summarizer_concurrency: int = Field(
        default=int(os.getenv("SUMMARIZER_CONCURRENCY", "2"))
    )
    summarizer_model: str = Field(
        default=os.getenv("SUMMARIZER_MODEL", "mixtral-8x7b-32768")
    )
    summarizer_temperature: float = Field(
        default=float(os.getenv("SUMMARIZER_TEMPERATURE", "0.2"))
    )
    summarizer_max_output_tokens: int = Field(
        default=int(os.getenv("SUMMARIZER_MAX_OUTPUT_TOKENS", "256"))
    )
    summarizer_request_timeout: float = Field(
        default=float(os.getenv("SUMMARIZER_REQUEST_TIMEOUT", "30"))
    )
    summarizer_max_retries: int = Field(
        default=int(os.getenv("SUMMARIZER_MAX_RETRIES", "3"))
    )
    summarizer_backoff_seconds: float = Field(
        default=float(os.getenv("SUMMARIZER_BACKOFF_SECONDS", "2.0"))
    )
    summarizer_daily_token_budget: int | None = Field(
        default=_optional_int_env("SUMMARIZER_DAILY_TOKEN_BUDGET")
    )

    entity_extraction_enabled: bool = Field(
        default=os.getenv("ENTITY_EXTRACTION_ENABLED", "true").lower() == "true"
    )
    entity_concurrency: int = Field(
        default=int(os.getenv("ENTITY_CONCURRENCY", "2"))
    )
    entity_queue_name: str = Field(
        default=os.getenv("ENTITY_QUEUE_NAME", "sec:groq:entity")
    )
    entity_queue_visibility_timeout_seconds: int = Field(
        default=int(os.getenv("ENTITY_QUEUE_VISIBILITY_TIMEOUT_SECONDS", "600"))
    )
    entity_queue_requeue_batch_size: int = Field(
        default=int(os.getenv("ENTITY_QUEUE_REQUEUE_BATCH_SIZE", "200"))
    )
    entity_queue_pause_threshold: int = Field(
        default=int(os.getenv("ENTITY_QUEUE_PAUSE_THRESHOLD", "1000"))
    )
    entity_queue_resume_threshold: int = Field(
        default=int(os.getenv("ENTITY_QUEUE_RESUME_THRESHOLD", "750"))
    )
    entity_backpressure_check_interval_seconds: float = Field(
        default=float(os.getenv("ENTITY_BACKPRESSURE_CHECK_INTERVAL_SECONDS", "1.0"))
    )
    entity_model: str = Field(
        default=os.getenv("ENTITY_MODEL", "llama-3.3-70b-versatile")
    )
    entity_temperature: float = Field(
        default=float(os.getenv("ENTITY_TEMPERATURE", "0"))
    )
    entity_max_output_tokens: int = Field(
        default=int(os.getenv("ENTITY_MAX_OUTPUT_TOKENS", "512"))
    )
    entity_request_timeout: float = Field(
        default=float(os.getenv("ENTITY_REQUEST_TIMEOUT", "30"))
    )
    entity_max_retries: int = Field(
        default=int(os.getenv("ENTITY_MAX_RETRIES", "3"))
    )
    entity_backoff_seconds: float = Field(
        default=float(os.getenv("ENTITY_BACKOFF_SECONDS", "2.0"))
    )
    entity_daily_token_budget: int | None = Field(
        default=_optional_int_env("ENTITY_DAILY_TOKEN_BUDGET")
    )

    diff_enabled: bool = Field(default=os.getenv("DIFF_ENABLED", "true").lower() == "true")
    diff_concurrency: int = Field(default=int(os.getenv("DIFF_CONCURRENCY", "2")))
    diff_queue_name: str = Field(default=os.getenv("DIFF_QUEUE_NAME", "sec:groq:diff"))
    diff_queue_visibility_timeout_seconds: int = Field(
        default=int(os.getenv("DIFF_QUEUE_VISIBILITY_TIMEOUT_SECONDS", "600"))
    )
    diff_queue_requeue_batch_size: int = Field(
        default=int(os.getenv("DIFF_QUEUE_REQUEUE_BATCH_SIZE", "200"))
    )
    diff_queue_pause_threshold: int = Field(
        default=int(os.getenv("DIFF_QUEUE_PAUSE_THRESHOLD", "1000"))
    )
    diff_queue_resume_threshold: int = Field(
        default=int(os.getenv("DIFF_QUEUE_RESUME_THRESHOLD", "750"))
    )
    diff_backpressure_check_interval_seconds: float = Field(
        default=float(os.getenv("DIFF_BACKPRESSURE_CHECK_INTERVAL_SECONDS", "1.0"))
    )
    diff_model: str = Field(default=os.getenv("DIFF_MODEL", "llama-3.3-70b-versatile"))
    diff_temperature: float = Field(
        default=float(os.getenv("DIFF_TEMPERATURE", "0.2"))
    )
    diff_max_output_tokens: int = Field(
        default=int(os.getenv("DIFF_MAX_OUTPUT_TOKENS", "512"))
    )
    diff_request_timeout: float = Field(
        default=float(os.getenv("DIFF_REQUEST_TIMEOUT", "30"))
    )
    diff_max_retries: int = Field(default=int(os.getenv("DIFF_MAX_RETRIES", "3")))
    diff_backoff_seconds: float = Field(
        default=float(os.getenv("DIFF_BACKOFF_SECONDS", "2.0"))
    )
    diff_daily_token_budget: int | None = Field(
        default=_optional_int_env("DIFF_DAILY_TOKEN_BUDGET")
    )

    minio_endpoint: str = Field(default=os.getenv("MINIO_ENDPOINT", "http://minio:9000"))
    minio_access_key: str = Field(default=os.getenv("MINIO_ACCESS_KEY", "filings"))
    minio_secret_key: str = Field(default=os.getenv("MINIO_SECRET_KEY", "filingsfilings"))
    minio_secure: bool = Field(
        default=os.getenv("MINIO_SECURE", "false").lower() == "true"
    )
    minio_region: str | None = Field(default=os.getenv("MINIO_REGION"))
    minio_filings_bucket: str = Field(
        default=os.getenv("MINIO_FILINGS_BUCKET", "filings-raw")
    )

    parser_enabled: bool = Field(
        default=os.getenv("PARSER_ENABLED", "true").lower() == "true"
    )
    parser_concurrency: int = Field(
        default=int(os.getenv("PARSER_CONCURRENCY", "2"))
    )
    parser_queue_name: str = Field(
        default=os.getenv("EDGAR_PARSE_QUEUE_NAME", "sec:ingestion:parse")
    )
    parser_max_retries: int = Field(
        default=int(os.getenv("PARSER_MAX_RETRIES", "3"))
    )
    parser_backoff_seconds: float = Field(
        default=float(os.getenv("PARSER_BACKOFF_SECONDS", "1.5"))
    )
    edgar_download_queue_pause_threshold: int = Field(
        default=int(os.getenv("EDGAR_DOWNLOAD_QUEUE_PAUSE_THRESHOLD", "500"))
    )
    edgar_download_queue_resume_threshold: int = Field(
        default=int(os.getenv("EDGAR_DOWNLOAD_QUEUE_RESUME_THRESHOLD", "350"))
    )
    edgar_backpressure_check_interval_seconds: float = Field(
        default=float(os.getenv("EDGAR_BACKPRESSURE_CHECK_INTERVAL_SECONDS", "1.0"))
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
