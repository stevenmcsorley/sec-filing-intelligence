"""Tests for OPA client integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from app.auth.opa import OPAClient
from fastapi import HTTPException


@pytest.fixture
def opa_client() -> OPAClient:
    """Create an OPA client instance for testing."""
    return OPAClient(opa_url="http://localhost:8181")


@pytest.fixture
def sample_user_context() -> dict:
    """Sample user context for testing."""
    return {
        "id": "user-123",
        "email": "test@example.com",
        "roles": ["analyst_pro"],
        "subscription": {"tier": "pro"},
        "org_id": "org-456",
    }


@pytest.mark.asyncio
async def test_check_permission_allows(opa_client: OPAClient, sample_user_context: dict) -> None:
    """Test that OPA client correctly handles allow decisions."""
    mock_response_allow = AsyncMock()
    mock_response_allow.status_code = 200
    mock_response_allow.json = lambda: {"result": True}
    mock_response_allow.raise_for_status = lambda: None

    mock_response_audit = AsyncMock()
    mock_response_audit.status_code = 200
    mock_response_audit.json = lambda: {
        "result": {
            "decision_id": "test-123",
            "user": sample_user_context,
            "action": "alerts:view",
            "resource": {},
            "allowed": True,
        }
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(
            side_effect=[mock_response_allow, mock_response_audit]
        )
        mock_client.return_value = mock_instance

        decision = await opa_client.check_permission(
            user_context=sample_user_context,
            action="alerts:view",
            resource={"org_id": "org-456"},
        )

        assert decision.allow is True
        assert decision.audit_log is not None
        assert decision.audit_log["allowed"] is True


@pytest.mark.asyncio
async def test_check_permission_denies(opa_client: OPAClient, sample_user_context: dict) -> None:
    """Test that OPA client correctly handles deny decisions."""
    mock_response_allow = AsyncMock()
    mock_response_allow.status_code = 200
    mock_response_allow.json = lambda: {"result": False}
    mock_response_allow.raise_for_status = lambda: None

    mock_response_audit = AsyncMock()
    mock_response_audit.status_code = 200
    mock_response_audit.json = lambda: {
        "result": {
            "decision_id": "test-123",
            "user": sample_user_context,
            "action": "admin:delete",
            "resource": {},
            "allowed": False,
        }
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(
            side_effect=[mock_response_allow, mock_response_audit]
        )
        mock_client.return_value = mock_instance

        decision = await opa_client.check_permission(
            user_context=sample_user_context,
            action="admin:delete",
        )

        assert decision.allow is False


@pytest.mark.asyncio
async def test_check_permission_opa_timeout(
    opa_client: OPAClient, sample_user_context: dict
) -> None:
    """Test that OPA client handles timeout errors appropriately."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        mock_client.return_value = mock_instance

        with pytest.raises(HTTPException) as exc_info:
            await opa_client.check_permission(
                user_context=sample_user_context,
                action="alerts:view",
            )

        assert exc_info.value.status_code == 503
        assert "unavailable" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_check_permission_opa_http_error(
    opa_client: OPAClient, sample_user_context: dict
) -> None:
    """Test that OPA client handles HTTP errors appropriately."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error", request=AsyncMock(), response=AsyncMock()
            )
        )
        mock_client.return_value = mock_instance

        with pytest.raises(HTTPException) as exc_info:
            await opa_client.check_permission(
                user_context=sample_user_context,
                action="alerts:view",
            )

        assert exc_info.value.status_code == 500
        assert "failed" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_super_admin_bypass(opa_client: OPAClient) -> None:
    """Test that super_admin role allows all actions."""
    super_admin_context = {
        "id": "admin-123",
        "email": "admin@example.com",
        "roles": ["super_admin"],
        "subscription": {"tier": "pro"},
        "org_id": "admin-org",
    }

    mock_response_allow = AsyncMock()
    mock_response_allow.status_code = 200
    mock_response_allow.json = lambda: {"result": True}
    mock_response_allow.raise_for_status = lambda: None

    mock_response_audit = AsyncMock()
    mock_response_audit.status_code = 200
    mock_response_audit.json = lambda: {"result": {}}

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(
            side_effect=[mock_response_allow, mock_response_audit]
        )
        mock_client.return_value = mock_instance

        decision = await opa_client.check_permission(
            user_context=super_admin_context,
            action="any:action",
        )

        assert decision.allow is True


@pytest.mark.asyncio
async def test_health_check_action_allowed(opa_client: OPAClient) -> None:
    """Test that health:read action is allowed for all users."""
    basic_user_context = {
        "id": "user-789",
        "email": "basic@example.com",
        "roles": ["basic_free"],
        "subscription": {"tier": "free"},
        "org_id": "org-789",
    }

    mock_response_allow = AsyncMock()
    mock_response_allow.status_code = 200
    mock_response_allow.json = lambda: {"result": True}
    mock_response_allow.raise_for_status = lambda: None

    mock_response_audit = AsyncMock()
    mock_response_audit.status_code = 200
    mock_response_audit.json = lambda: {"result": {}}

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_instance.post = AsyncMock(
            side_effect=[mock_response_allow, mock_response_audit]
        )
        mock_client.return_value = mock_instance

        decision = await opa_client.check_permission(
            user_context=basic_user_context,
            action="health:read",
        )

        assert decision.allow is True
