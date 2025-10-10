from __future__ import annotations

from pydantic import BaseModel


class TokenContext(BaseModel):
    """Normalized details extracted from a verified Keycloak access token."""

    subject: str
    email: str | None = None
    roles: list[str]
    token: str
    expires_at: int | None = None
