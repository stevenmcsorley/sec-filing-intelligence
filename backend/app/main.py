from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth.router import router as auth_router
from .config import get_settings
from .db import close_db, init_db
from .ingestion import IngestionService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle: startup and shutdown events."""
    # Startup
    settings = get_settings()
    init_db(settings)
    ingestion_service = IngestionService(settings)
    await ingestion_service.start()
    app.state.ingestion_service = ingestion_service
    yield
    # Shutdown
    await app.state.ingestion_service.stop()  # type: ignore[attr-defined]
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
