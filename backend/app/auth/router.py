from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from .dependencies import get_current_token, get_openid_client
from .models import TokenContext
from .openid import KeycloakOpenIDClient

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/health")
async def auth_health(
    openid_client: Annotated[KeycloakOpenIDClient, Depends(get_openid_client)],
) -> dict[str, str]:
    await openid_client.check_health()
    return {"status": "ok"}


@router.get("/me")
async def auth_me(
    token: Annotated[TokenContext, Depends(get_current_token)],
) -> dict[str, object]:
    return {
        "sub": token.subject,
        "email": token.email,
        "roles": token.roles,
        "exp": token.expires_at,
    }
