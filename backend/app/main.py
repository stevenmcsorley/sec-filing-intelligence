from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

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
    state = cast(Any, app.state)
    state.ingestion_service = ingestion_service
    yield
    # Shutdown
    state = cast(Any, app.state)
    service = getattr(state, "ingestion_service", None)
    if service is not None:
        await service.stop()
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
