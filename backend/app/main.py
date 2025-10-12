from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.router import router as auth_router
from .config import get_settings
from .db import init_db
from .diff import DiffService
from .downloader import DownloadService
from .entities import EntityExtractionService
from .filings import router as filings_router
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
    entity_service = EntityExtractionService(settings)
    await entity_service.start()
    diff_service = DiffService(settings)
    await diff_service.start()
    state = cast(Any, app.state)
    state.ingestion_service = ingestion_service
    state.download_service = download_service
    state.parser_service = parser_service
    state.entity_service = entity_service
    state.summary_service = summary_service
    state.diff_service = diff_service
    yield
    # Shutdown


app = FastAPI(
    title="SEC Filing Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(filings_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic readiness probe used by compose, k8s, and CI smoke tests."""
    return {"status": "ok"}
