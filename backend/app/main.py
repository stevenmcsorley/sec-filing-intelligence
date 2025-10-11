from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI

from .auth.router import router as auth_router
from .config import get_settings
from .db import close_db, init_db
from .downloader import DownloadService
from .ingestion import IngestionService
from .parsing import ParserService
from .summarization import SectionSummaryService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: startup and shutdown events."""
    # Startup
    settings = get_settings()
    init_db(settings)
    ingestion_service = IngestionService(settings)
    await ingestion_service.start()
    download_service = DownloadService(settings)
    await download_service.start()
    parser_service = ParserService(settings)
    await parser_service.start()
    summary_service = SectionSummaryService(settings)
    await summary_service.start()
    state = cast(Any, app.state)
    state.ingestion_service = ingestion_service
    state.download_service = download_service
    state.parser_service = parser_service
    state.summary_service = summary_service
    yield
    # Shutdown
    state = cast(Any, app.state)
    current_parser_service = cast(ParserService | None, getattr(state, "parser_service", None))
    if current_parser_service is not None:
        await current_parser_service.stop()
    current_summary_service = cast(
        SectionSummaryService | None, getattr(state, "summary_service", None)
    )
    if current_summary_service is not None:
        await current_summary_service.stop()
    current_download_service = cast(
        DownloadService | None,
        getattr(state, "download_service", None),
    )
    if current_download_service is not None:
        await current_download_service.stop()
    current_ingestion_service = cast(
        IngestionService | None,
        getattr(state, "ingestion_service", None),
    )
    if current_ingestion_service is not None:
        await current_ingestion_service.stop()
    await close_db()


app = FastAPI(
    title="SEC Filing Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic readiness probe used by compose, k8s, and CI smoke tests."""
    return {"status": "ok"}
