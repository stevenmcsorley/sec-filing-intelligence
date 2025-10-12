"""Repository for organization, user membership, and subscription operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Organization, Subscription, UserOrganization

if TYPE_CHECKING:
    from ..auth.models import TokenContext


class OrganizationRepository:
    """Repository for organization-related database operations."""

    def __init__(self, db_session: AsyncSession) -> None:
        """Initialize repository with database session."""
        self.db_session = db_session

    async def get_user_organization_with_subscription(
        self, user_id: str
    ) -> tuple[Organization, UserOrganization, Subscription] | None:
        """Get user's organization membership with subscription details.

        Args:
            user_id: Keycloak user subject (UUID string)

        Returns:
            Tuple of (organization, user_membership, subscription) or None if not found
        """
        stmt = (
            select(UserOrganization)
            .where(UserOrganization.user_id == user_id)
            .options(
                selectinload(UserOrganization.organization).selectinload(
                    Organization.subscription
                )
            )
        )

        result = await self.db_session.execute(stmt)
        user_org = result.scalar_one_or_none()

        if user_org is None or user_org.organization is None:
            return None

        subscription = user_org.organization.subscription
        if subscription is None:
            return None

        return (user_org.organization, user_org, subscription)

    async def get_user_context_for_token(
        self, token: TokenContext
    ) -> dict[str, object] | None:
        """Get user context for OPA policy evaluation from token.

        Args:
            token: JWT token context from Keycloak

        Returns:
            User context dict for OPA or None if user not found in any org
        """
        result = await self.get_user_organization_with_subscription(token.subject)

        if result is None:
            return None

        organization, user_org, subscription = result

        return {
            "id": token.subject,
            "email": token.email,
            "roles": token.roles,
            "subscription": {"tier": subscription.tier},
            "org_id": organization.slug,  # Use slug as org_id for OPA
        }