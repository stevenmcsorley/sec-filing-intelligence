from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db_session
from ..repositories import OrganizationRepository
from .dependencies import get_current_token, get_openid_client
from .models import TokenContext
from .opa import OPAClient, OPADecision, get_opa_client
from .openid import KeycloakOpenIDClient

router = APIRouter(prefix="/auth", tags=["auth"])


async def token_to_user_context(
    token: TokenContext,
    db: AsyncSession,
) -> dict[str, Any]:
    """Convert TokenContext to OPA user context format.

    Queries real user organization and subscription data from database.
    Falls back to default values if user not found (for bootstrap/development).
    """
    repo = OrganizationRepository(db)
    user_context = await repo.get_user_context_for_token(token)

    if user_context is not None:
        return user_context

    # Fallback for users not in any organization (bootstrap/development)
    return {
        "id": token.subject,
        "email": token.email,
        "roles": token.roles,
        "subscription": {"tier": "free"},  # Default tier for unknown users
        "org_id": "default",  # Default org for unknown users
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
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OPADecision:
    """Test endpoint to check OPA permissions for debugging.

    Example: GET /auth/check-permission?action=alerts:view
    """
    user_context = await token_to_user_context(token, db)
    decision = await opa_client.check_permission(user_context, action)
    return decision
