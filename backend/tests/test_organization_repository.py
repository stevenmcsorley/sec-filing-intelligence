"""Tests for organization repository."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.repositories import OrganizationRepository
from app.models import Organization, Subscription, UserOrganization
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_user_context_for_token_with_membership(db_session: AsyncSession) -> None:
    """Test getting user context for a user with organization membership."""
    # Create test organization
    org = Organization(
        name="Test Org",
        slug="test-org-repo",
        created_at=datetime.now(UTC),
    )
    db_session.add(org)
    await db_session.flush()

    # Create subscription
    subscription = Subscription(
        organization_id=org.id,
        tier="pro",
        features='{"real_time_alerts": true}',
        limits='{"max_tickers": 200}',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(subscription)
    await db_session.flush()

    # Create user membership
    user_org = UserOrganization(
        user_id="test-user-123",
        organization_id=org.id,
        role="analyst_pro",
        joined_at=datetime.now(UTC),
    )
    db_session.add(user_org)
    await db_session.commit()

    # Test repository
    repo = OrganizationRepository(db_session)

    from app.auth.models import TokenContext
    token = TokenContext(
        subject="test-user-123",
        email="test@example.com",
        roles=["analyst_pro"],
        token="fake-jwt-token",
        expires_at=int(datetime.now(UTC).timestamp()),
    )

    user_context = await repo.get_user_context_for_token(token)

    assert user_context is not None
    assert user_context["id"] == "test-user-123"
    assert user_context["email"] == "test@example.com"
    assert user_context["roles"] == ["analyst_pro"]
    assert user_context["subscription"]["tier"] == "pro"
    assert user_context["org_id"] == "test-org-repo"


@pytest.mark.asyncio
async def test_get_user_context_for_token_no_membership(db_session: AsyncSession) -> None:
    """Test getting user context for a user without organization membership."""
    repo = OrganizationRepository(db_session)

    from app.auth.models import TokenContext
    token = TokenContext(
        subject="unknown-user",
        email="unknown@example.com",
        roles=["basic_free"],
        token="fake-jwt-token-2",
        expires_at=int(datetime.now(UTC).timestamp()),
    )

    user_context = await repo.get_user_context_for_token(token)

    assert user_context is None


@pytest.mark.asyncio
async def test_get_user_organization_with_subscription(db_session: AsyncSession) -> None:
    """Test getting user organization with subscription details."""
    # Create test organization
    org = Organization(
        name="Test Org 2",
        slug="test-org-repo-2",
        created_at=datetime.now(UTC),
    )
    db_session.add(org)
    await db_session.flush()

    # Create subscription
    subscription = Subscription(
        organization_id=org.id,
        tier="free",
        features='{"real_time_alerts": false}',
        limits='{"max_tickers": 5}',
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(subscription)
    await db_session.flush()

    # Create user membership
    user_org = UserOrganization(
        user_id="test-user-456",
        organization_id=org.id,
        role="basic_free",
        joined_at=datetime.now(UTC),
    )
    db_session.add(user_org)
    await db_session.commit()

    # Test repository
    repo = OrganizationRepository(db_session)

    result = await repo.get_user_organization_with_subscription("test-user-456")

    assert result is not None
    organization, user_membership, subscription_result = result
    assert organization.slug == "test-org-repo-2"
    assert user_membership.role == "basic_free"
    assert subscription_result.tier == "free"