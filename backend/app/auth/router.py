from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from .dependencies import get_current_token, get_openid_client
from .models import TokenContext
from .opa import OPAClient, OPADecision, get_opa_client
from .openid import KeycloakOpenIDClient

router = APIRouter(prefix="/auth", tags=["auth"])


def token_to_user_context(token: TokenContext) -> dict[str, Any]:
    """Convert TokenContext to OPA user context format."""
    return {
        "id": token.subject,
        "email": token.email,
        "roles": token.roles,
        "subscription": {"tier": "free"},  # TODO: fetch from DB
        "org_id": "default",  # TODO: fetch from token claims or DB
    }


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


@router.get("/check-permission")
async def check_permission(
    action: str,
    token: Annotated[TokenContext, Depends(get_current_token)],
    opa_client: Annotated[OPAClient, Depends(get_opa_client)],
) -> OPADecision:
    """Test endpoint to check OPA permissions for debugging.

    Example: GET /auth/check-permission?action=alerts:view
    """
    user_context = token_to_user_context(token)
    decision = await opa_client.check_permission(user_context, action)
    return decision
