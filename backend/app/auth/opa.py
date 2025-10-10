"""OPA (Open Policy Agent) client for authorization decisions.

This module provides a FastAPI dependency that calls OPA to evaluate
authorization policies. All policy decisions are logged for audit purposes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


class OPAInput(BaseModel):
    """Input payload sent to OPA for policy evaluation."""

    decision_id: str
    user: dict[str, Any]
    action: str
    resource: dict[str, Any]


class OPADecision(BaseModel):
    """Response from OPA policy evaluation."""

    allow: bool
    audit_log: dict[str, Any] | None = None


class OPAClient:
    """Client for making authorization decisions via OPA."""

    def __init__(self, opa_url: str) -> None:
        """Initialize the OPA client.

        Args:
            opa_url: Base URL of the OPA server (e.g., http://opa:8181)
        """
        self.opa_url = opa_url.rstrip("/")
        self.policy_path = "/v1/data/authz/allow"
        self.audit_path = "/v1/data/authz/audit_log"

    async def check_permission(
        self,
        user_context: dict[str, Any],
        action: str,
        resource: dict[str, Any] | None = None,
    ) -> OPADecision:
        """Check if a user is authorized to perform an action on a resource.

        Args:
            user_context: User information including roles, org_id, subscription tier
            action: Action being performed (e.g., "alerts:view", "filings:read")
            resource: Optional resource metadata (org_id, impact_score, etc.)

        Returns:
            OPADecision with allow boolean and audit information

        Raises:
            HTTPException: If OPA is unreachable or returns an error
        """
        decision_id = str(uuid.uuid4())

        opa_input = OPAInput(
            decision_id=decision_id,
            user=user_context,
            action=action,
            resource=resource or {},
        )

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.post(
                    f"{self.opa_url}{self.policy_path}",
                    json={"input": opa_input.model_dump()},
                )
                response.raise_for_status()

                result = response.json()
                allow = result.get("result", False)

                # Fetch audit log separately
                audit_response = await client.post(
                    f"{self.opa_url}{self.audit_path}",
                    json={"input": opa_input.model_dump()},
                )
                audit_log = (
                    audit_response.json().get("result")
                    if audit_response.status_code == 200
                    else None
                )

                decision = OPADecision(allow=allow, audit_log=audit_log)

                # Log the decision for observability
                logger.info(
                    "OPA decision",
                    extra={
                        "decision_id": decision_id,
                        "action": action,
                        "allow": allow,
                        "user_id": user_context.get("id"),
                        "roles": user_context.get("roles"),
                    },
                )

                return decision

        except httpx.TimeoutException as exc:
            logger.error(f"OPA timeout for decision {decision_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authorization service unavailable",
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(f"OPA HTTP error for decision {decision_id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authorization check failed",
            ) from exc


async def get_opa_client(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> OPAClient:
    """FastAPI dependency that provides an OPA client.

    Args:
        settings: Application settings with OPA URL configuration

    Returns:
        Configured OPAClient instance

    Raises:
        HTTPException: If OPA URL is not configured
    """
    if not settings.opa_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPA not configured",
        )

    return OPAClient(opa_url=str(settings.opa_url))


async def require_permission(
    action: str,
    user_context: dict[str, Any],
    resource: dict[str, Any] | None = None,
    opa_client: OPAClient = Depends(get_opa_client),  # noqa: B008
) -> OPADecision:
    """FastAPI dependency that enforces authorization via OPA.

    Args:
        action: Action being performed
        user_context: User information from JWT token
        resource: Optional resource metadata
        opa_client: OPA client instance

    Returns:
        OPADecision if allowed

    Raises:
        HTTPException: 403 if permission denied, 503 if OPA unavailable
    """
    decision = await opa_client.check_permission(user_context, action, resource)

    if not decision.allow:
        logger.warning(
            f"Permission denied for action '{action}'",
            extra={
                "user_id": user_context.get("id"),
                "roles": user_context.get("roles"),
                "action": action,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return decision
