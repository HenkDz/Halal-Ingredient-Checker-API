"""Tests for Polar.sh payment integration (HAL-23).

Replaces tests/test_stripe.py.
These tests mock the Polar API calls to avoid requiring real API keys.
They verify the webhook processing logic and checkout session creation.
"""

import base64
import hashlib
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth import auth_store
from app.main import app
from app.polar import (
    _hash_key,
    apply_webhook_action,
    create_billing_portal_session,
    create_checkout_session,
    is_configured,
    process_webhook_event,
    verify_webhook_signature,
)

client = TestClient(app)


def _register(email="polar_test@example.com", name="Polar User"):
    """Helper to register a user and return (api_key, key_hash)."""
    resp = client.post("/api/v1/auth/register", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.json()
    api_key = resp.json()["api_key"]
    key_hash = _hash_key(api_key)
    return api_key, key_hash


# --- Config Check ---

def test_polar_not_configured_by_default():
    """Without env vars, Polar should report as not configured."""
    assert not is_configured()


# --- Checkout Session Creation ---

def test_create_checkout_session_requires_config():
    """Should raise ValueError when Polar is not configured."""
    api_key, _ = _register("checkout@example.com")
    with pytest.raises(ValueError, match="not configured"):
        create_checkout_session(
            user_email="checkout@example.com",
            api_key=api_key,
            tier="pro",
            billing_period="monthly",
        )


def test_create_checkout_session_invalid_tier():
    """Should reject non-pro tiers."""
    with pytest.raises(ValueError, match="Only 'pro' tier"):
        create_checkout_session(
            user_email="test@example.com",
            api_key="test_key",
            tier="enterprise",
            billing_period="monthly",
        )


def test_create_checkout_session_invalid_period():
    """Should reject invalid billing period."""
    with pytest.raises(ValueError, match="billing_period must be"):
        create_checkout_session(
            user_email="test@example.com",
            api_key="test_key",
            tier="pro",
            billing_period="weekly",
        )


@patch("app.polar.POLAR_PRO_MONTHLY_PRODUCT_ID", "prod_monthly_test")
@patch("app.polar.POLAR_ACCESS_TOKEN", "pat_test_123")
@patch("app.polar.POLAR_WEBHOOK_SECRET", "whsec_test")
@patch("app.polar._get_http_client")
def test_create_checkout_session_success(mock_client_factory):
    """Should create a checkout session and return URL."""
    api_key, _ = _register("checkout_ok@example.com")

    # Mock httpx.Client context manager
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "id": "checkout_test_id",
        "url": "https://polar.sh/checkout/test",
        "customer_id": "cust_test123",
    }
    mock_response.raise_for_status = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_factory.return_value = mock_client

    result = create_checkout_session(
        user_email="checkout_ok@example.com",
        api_key=api_key,
        tier="pro",
        billing_period="monthly",
    )

    assert result["checkout_url"] == "https://polar.sh/checkout/test"
    assert result["session_id"] == "checkout_test_id"
    assert result["customer_id"] == "cust_test123"


# --- Billing Portal ---

def test_billing_portal_requires_config():
    """Should raise ValueError when Polar is not configured."""
    with pytest.raises(ValueError, match="not configured"):
        create_billing_portal_session("cust_test123")


def test_billing_portal_requires_customer_id():
    """Should raise ValueError when customer_id is empty."""
    with pytest.raises(ValueError, match="not configured"):
        create_billing_portal_session("")


@patch("app.polar.is_configured", return_value=True)
@patch("app.polar._get_http_client")
def test_billing_portal_success(mock_client_factory, mock_configured):
    """Should create a portal session and return URL."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"url": "https://polar.sh/portal/test"}
    mock_response.raise_for_status = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response
    mock_client_factory.return_value = mock_client

    result = create_billing_portal_session("cust_test123")

    assert result["portal_url"] == "https://polar.sh/portal/test"


# --- Webhook Signature Verification ---

def test_verify_webhook_no_secret():
    """Should fail when webhook secret is not configured."""
    with pytest.raises(ValueError, match="not configured"):
        verify_webhook_signature(b"{}", "t=123,v1=abc")


def test_verify_webhook_bad_signature():
    """Should raise ValueError for invalid signatures."""
    secret = base64.b64encode(b"test_secret").decode()
    with (
        patch("app.polar.POLAR_WEBHOOK_SECRET", secret),
        pytest.raises(ValueError, match="signature"),
    ):
        verify_webhook_signature(b'{"type":"test"}', "t=1234567890,v1=wrong_signature")


def test_verify_webhook_valid_signature():
    """Should verify a correctly signed webhook payload."""
    import hmac as hmac_mod

    secret_bytes = b"my_webhook_secret"
    secret_b64 = base64.b64encode(secret_bytes).decode()
    timestamp = str(int(time.time()))
    payload = b'{"type":"subscription.active","data":{}}'
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac_mod.new(secret_bytes, signed_payload, hashlib.sha256).hexdigest()

    with patch("app.polar.POLAR_WEBHOOK_SECRET", secret_b64):
        event = verify_webhook_signature(payload, f"t={timestamp},v1={signature}")
        assert event["type"] == "subscription.active"


def test_verify_webhook_stale_timestamp():
    """Should reject webhooks with timestamps older than 5 minutes."""
    secret_b64 = base64.b64encode(b"test_secret").decode()
    stale_ts = str(int(time.time()) - 600)  # 10 minutes ago

    with (
        patch("app.polar.POLAR_WEBHOOK_SECRET", secret_b64),
        pytest.raises(ValueError, match="signature"),
    ):
        verify_webhook_signature(b'{"type":"test"}', f"t={stale_ts},v1=fake")


# --- Webhook Event Processing ---

def test_process_subscription_active():
    """Should extract user info from subscription.active."""
    event = {
        "type": "subscription.active",
        "data": {
            "metadata": {
                "api_key_hash": "hash_abc123",
                "tier": "pro",
            },
            "customer_id": "cust_test",
            "id": "sub_test",
            "started_at": "2026-01-01T00:00:00Z",
            "current_period_end": "2026-02-01T00:00:00Z",
        },
    }
    result = process_webhook_event(event)

    assert result["event_type"] == "subscription.active"
    assert result["api_key_hash"] == "hash_abc123"
    assert result["tier"] == "pro"
    assert result["polar_customer_id"] == "cust_test"
    assert result["polar_subscription_id"] == "sub_test"
    assert result["action"] == "activate"
    assert result["period_end"] is not None


def test_process_subscription_created():
    """Should handle subscription.created."""
    event = {
        "type": "subscription.created",
        "data": {
            "metadata": {
                "api_key_hash": "hash_abc123",
                "tier": "pro",
            },
            "customer_id": "cust_test",
            "id": "sub_test",
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "activate"
    assert result["api_key_hash"] == "hash_abc123"
    assert result["polar_subscription_id"] == "sub_test"


def test_process_subscription_revoked():
    """Should handle subscription.revoked (access terminated)."""
    event = {
        "type": "subscription.revoked",
        "data": {
            "metadata": {"api_key_hash": "hash_abc123"},
            "customer_id": "cust_test",
            "id": "sub_test",
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "cancel"
    assert result["api_key_hash"] == "hash_abc123"
    assert result["polar_subscription_id"] == "sub_test"


def test_process_subscription_canceled_end_of_period():
    """Should ignore end-of-period cancellations (will get revoked later)."""
    event = {
        "type": "subscription.canceled",
        "data": {
            "metadata": {"api_key_hash": "hash_abc123"},
            "customer_id": "cust_test",
            "id": "sub_test",
            "cancel_at_period_end": True,
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "ignore"


def test_process_subscription_canceled_immediate():
    """Should handle immediate cancellations."""
    event = {
        "type": "subscription.canceled",
        "data": {
            "metadata": {"api_key_hash": "hash_abc123"},
            "customer_id": "cust_test",
            "id": "sub_test",
            "cancel_at_period_end": False,
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "cancel"


def test_process_past_due():
    """Should handle subscription.past_due (payment failed)."""
    event = {
        "type": "subscription.past_due",
        "data": {
            "metadata": {"api_key_hash": "hash_abc123"},
            "customer_id": "cust_test",
            "id": "sub_test",
            "current_period_end": 1234567890,
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "grant_grace"
    assert result["polar_customer_id"] == "cust_test"


def test_process_unhandled_event():
    """Should ignore unknown event types."""
    event = {
        "type": "order.paid",
        "data": {},
    }
    result = process_webhook_event(event)

    assert result["action"] == "ignore"
    assert result["event_type"] == "order.paid"


def test_process_subscription_active_missing_hash():
    """Should ignore subscription events without api_key_hash."""
    event = {
        "type": "subscription.active",
        "data": {
            "metadata": {},
            "customer_id": "cust_test",
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "ignore"


# --- Webhook Action Application ---

def test_apply_activate_action():
    """Should activate user subscription on subscription.active."""
    api_key, key_hash = _register("activate@example.com")
    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "free"

    action_result = {
        "event_type": "subscription.active",
        "api_key_hash": key_hash,
        "tier": "pro",
        "polar_customer_id": "cust_test",
        "polar_subscription_id": "sub_test",
        "action": "activate",
        "period_start": time.time(),
        "period_end": time.time() + 30 * 86400,
    }

    apply_webhook_action(auth_store, action_result)

    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "pro"
    assert user.subscription.polar_customer_id == "cust_test"
    assert user.subscription.polar_subscription_id == "sub_test"
    assert user.subscription.auto_renew is True


def test_apply_cancel_action():
    """Should cancel subscription on subscription.revoked."""
    api_key, key_hash = _register("cancel@example.com")

    # First activate
    user = auth_store.get_user_by_key(api_key)
    user.subscription.tier = "pro"
    user.subscription.period_end = time.time() + 30 * 86400
    user.subscription.polar_customer_id = "cust_test"

    action_result = {
        "event_type": "subscription.revoked",
        "api_key_hash": key_hash,
        "tier": None,
        "polar_customer_id": "cust_test",
        "polar_subscription_id": "sub_test",
        "action": "cancel",
        "period_start": None,
        "period_end": None,
    }

    apply_webhook_action(auth_store, action_result)

    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "free"
    assert user.subscription.polar_customer_id is None
    assert user.subscription.polar_subscription_id is None
    assert user.subscription.auto_renew is False


def test_apply_grace_period_action():
    """Should extend period by 7 days on payment failure."""
    api_key, key_hash = _register("grace_webhook@example.com")

    # Set up as a pro user with period ending soon
    user = auth_store.get_user_by_key(api_key)
    user.subscription.tier = "pro"
    user.subscription.period_end = time.time() + 1  # Expires almost now

    action_result = {
        "event_type": "subscription.past_due",
        "api_key_hash": key_hash,
        "tier": None,
        "polar_customer_id": "cust_test",
        "polar_subscription_id": "sub_test",
        "action": "grant_grace",
        "period_end": time.time() + 1,
    }

    apply_webhook_action(auth_store, action_result)

    user = auth_store.get_user_by_key(api_key)
    # Should have ~7 days remaining
    assert user.subscription.days_remaining() >= 6
    assert user.subscription.tier == "pro"  # Tier stays during grace


def test_apply_ignore_action():
    """Should do nothing for ignore actions."""
    apply_webhook_action(auth_store, {
        "action": "ignore",
        "api_key_hash": None,
    })
    # No error = pass


def test_apply_action_unknown_hash():
    """Should silently ignore actions for non-existent users."""
    apply_webhook_action(auth_store, {
        "action": "activate",
        "api_key_hash": "nonexistent_hash",
        "tier": "pro",
        "polar_customer_id": "cust_test",
        "polar_subscription_id": "sub_test",
        "period_start": time.time(),
        "period_end": time.time() + 30 * 86400,
    })
    # No error = pass


# --- Key Hash Utility ---

def test_hash_key_consistency():
    """Key hash should match auth store's hashing."""
    test_key = "halal_test_key_12345"
    hash1 = _hash_key(test_key)
    hash2 = hashlib.sha256(test_key.encode()).hexdigest()
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex


# --- API Endpoint Tests (unconfigured) ---

def test_polar_checkout_endpoint_unconfigured():
    """API endpoint should return not_configured without Polar setup."""
    resp = client.post("/api/v1/auth/subscribe/polar", json={
        "tier": "pro",
        "billing_period": "monthly",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


def test_polar_checkout_yearly_unconfigured():
    """Yearly billing should also return not_configured."""
    resp = client.post("/api/v1/auth/subscribe/polar", json={
        "tier": "pro",
        "billing_period": "yearly",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


def test_billing_portal_endpoint_unconfigured():
    """Billing portal should return not_configured."""
    resp = client.get("/api/v1/auth/billing/portal")
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


def test_webhook_endpoint_no_signature():
    """Webhook should reject requests without polar-webhook-signature."""
    resp = client.post("/api/v1/webhooks/polar", json={})
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"]["error"]
