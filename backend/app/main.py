from fastapi import FastAPI

from .auth.router import router as auth_router

app = FastAPI(
    title="SEC Filing Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(auth_router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Basic readiness probe used by compose, k8s, and CI smoke tests."""
    return {"status": "ok"}
