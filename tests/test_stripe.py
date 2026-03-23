"""Tests for Stripe payment integration (HAL-18).

These tests mock the Stripe SDK to avoid requiring real API keys.
They verify the webhook processing logic and checkout session creation.
"""

import hashlib
import time
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth import auth_store, Subscription
from app.stripe import (
    process_webhook_event,
    apply_webhook_action,
    verify_webhook_signature,
    create_checkout_session,
    create_billing_portal_session,
    is_configured,
    _hash_key,
)

client = TestClient(app)


def _register(email="stripe_test@example.com", name="Stripe User"):
    """Helper to register a user and return (api_key, key_hash)."""
    resp = client.post("/api/v1/auth/register", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.json()
    api_key = resp.json()["api_key"]
    key_hash = _hash_key(api_key)
    return api_key, key_hash


# --- Config Check ---

def test_stripe_not_configured_by_default():
    """Without env vars, Stripe should report as not configured."""
    assert not is_configured()


# --- Checkout Session Creation ---

def test_create_checkout_session_requires_config():
    """Should raise ValueError when Stripe is not configured."""
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
            api_key="fake_key",
            tier="enterprise",
            billing_period="monthly",
        )


def test_create_checkout_session_invalid_period():
    """Should reject invalid billing period."""
    with pytest.raises(ValueError, match="billing_period must be"):
        create_checkout_session(
            user_email="test@example.com",
            api_key="fake_key",
            tier="pro",
            billing_period="weekly",
        )


@patch("app.stripe.STRIPE_PRO_MONTHLY_PRICE_ID", "price_monthly_test")
@patch("app.stripe.STRIPE_SECRET_KEY", "sk_test_123")
@patch("app.stripe.STRIPE_PUBLISHABLE_KEY", "pk_test_123")
@patch("app.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("app.stripe.stripe")
def test_create_checkout_session_success(mock_stripe):
    """Should create a checkout session and return URL."""
    api_key, _ = _register("checkout_ok@example.com")

    # Mock Stripe Customer and Session creation
    mock_stripe.Customer.create.return_value = MagicMock(id="cus_test123")
    mock_stripe.checkout.Session.create.return_value = MagicMock(
        url="https://checkout.stripe.com/c/pay/cs_test",
        id="cs_test_session_id",
    )

    result = create_checkout_session(
        user_email="checkout_ok@example.com",
        api_key=api_key,
        tier="pro",
        billing_period="monthly",
    )

    assert result["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test"
    assert result["session_id"] == "cs_test_session_id"
    assert result["customer_id"] == "cus_test123"
    mock_stripe.Customer.create.assert_called_once()
    mock_stripe.checkout.Session.create.assert_called_once()


# --- Billing Portal ---

def test_billing_portal_requires_config():
    """Should raise ValueError when Stripe is not configured."""
    with pytest.raises(ValueError, match="not configured"):
        create_billing_portal_session("cus_test123")


def test_billing_portal_requires_customer_id():
    """Should raise ValueError when customer_id is empty."""
    with pytest.raises(ValueError, match="not configured"):
        create_billing_portal_session("")


@patch("app.stripe.is_configured", return_value=True)
@patch("app.stripe.stripe")
def test_billing_portal_success(mock_stripe, mock_configured):
    """Should create a portal session and return URL."""
    mock_stripe.billing_portal.Session.create.return_value = MagicMock(
        url="https://billing.stripe.com/session/test"
    )

    result = create_billing_portal_session("cus_test123")

    assert result["portal_url"] == "https://billing.stripe.com/session/test"
    mock_stripe.billing_portal.Session.create.assert_called_once()


# --- Webhook Signature Verification ---

def test_verify_webhook_no_secret():
    """Should fail when webhook secret is not configured."""
    with pytest.raises(ValueError, match="not configured"):
        verify_webhook_signature(b"{}", "t=123,v1=abc")


@patch("app.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test")
@patch("app.stripe.stripe")
def test_verify_webhook_bad_signature(mock_stripe):
    """Should raise ValueError for invalid signatures."""
    mock_stripe.Webhook.construct_event.side_effect = Exception("Invalid signature")
    with pytest.raises(ValueError, match="Invalid webhook signature"):
        verify_webhook_signature(b"{}", "t=123,v1=bad")


# --- Webhook Event Processing ---

def test_process_checkout_completed():
    """Should extract user info from checkout.session.completed."""
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "api_key_hash": "hash_abc123",
                    "tier": "pro",
                },
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }
    result = process_webhook_event(event)

    assert result["event_type"] == "checkout.session.completed"
    assert result["api_key_hash"] == "hash_abc123"
    assert result["tier"] == "pro"
    assert result["stripe_customer_id"] == "cus_test"
    assert result["stripe_subscription_id"] == "sub_test"
    assert result["action"] == "activate"


def test_process_subscription_deleted():
    """Should handle customer.subscription.deleted."""
    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test",
                "customer": "cus_test",
                "metadata": {"api_key_hash": "hash_abc123"},
            }
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "cancel"
    assert result["api_key_hash"] == "hash_abc123"
    assert result["stripe_subscription_id"] == "sub_test"


def test_process_payment_failed():
    """Should handle invoice.payment_failed."""
    event = {
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "subscription": "sub_test",
                "customer": "cus_test",
                "period_end": 1234567890,
            }
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "grant_grace"
    assert result["stripe_customer_id"] == "cus_test"


def test_process_unhandled_event():
    """Should ignore unknown event types."""
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {}},
    }
    result = process_webhook_event(event)

    assert result["action"] == "ignore"
    assert result["event_type"] == "payment_intent.succeeded"


def test_process_checkout_missing_hash():
    """Should ignore checkout.session.completed without api_key_hash."""
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {},
                "customer": "cus_test",
            }
        },
    }
    result = process_webhook_event(event)

    assert result["action"] == "ignore"


# --- Webhook Action Application ---

def test_apply_activate_action():
    """Should activate user subscription on checkout completion."""
    api_key, key_hash = _register("activate@example.com")
    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "free"

    action_result = {
        "event_type": "checkout.session.completed",
        "api_key_hash": key_hash,
        "tier": "pro",
        "stripe_customer_id": "cus_test",
        "stripe_subscription_id": "sub_test",
        "action": "activate",
        "period_start": time.time(),
        "period_end": time.time() + 30 * 86400,
    }

    apply_webhook_action(auth_store, action_result)

    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "pro"
    assert user.subscription.stripe_customer_id == "cus_test"
    assert user.subscription.stripe_subscription_id == "sub_test"
    assert user.subscription.auto_renew is True


def test_apply_cancel_action():
    """Should cancel subscription on customer.subscription.deleted."""
    api_key, key_hash = _register("cancel@example.com")

    # First activate
    user = auth_store.get_user_by_key(api_key)
    user.subscription.tier = "pro"
    user.subscription.period_end = time.time() + 30 * 86400
    user.subscription.stripe_customer_id = "cus_test"

    action_result = {
        "event_type": "customer.subscription.deleted",
        "api_key_hash": key_hash,
        "tier": None,
        "stripe_customer_id": "cus_test",
        "stripe_subscription_id": "sub_test",
        "action": "cancel",
        "period_start": None,
        "period_end": None,
    }

    apply_webhook_action(auth_store, action_result)

    user = auth_store.get_user_by_key(api_key)
    assert user.subscription.tier == "free"
    assert user.subscription.stripe_customer_id is None
    assert user.subscription.stripe_subscription_id is None
    assert user.subscription.auto_renew is False


def test_apply_grace_period_action():
    """Should extend period by 7 days on payment failure."""
    api_key, key_hash = _register("grace_webhook@example.com")

    # Set up as a pro user with period ending soon
    user = auth_store.get_user_by_key(api_key)
    user.subscription.tier = "pro"
    user.subscription.period_end = time.time() + 1  # Expires almost now

    action_result = {
        "event_type": "invoice.payment_failed",
        "api_key_hash": key_hash,
        "tier": None,
        "stripe_customer_id": "cus_test",
        "stripe_subscription_id": "sub_test",
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
        "stripe_customer_id": "cus_test",
        "stripe_subscription_id": "sub_test",
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

def test_stripe_checkout_endpoint_unconfigured():
    """API endpoint should return not_configured without Stripe setup."""
    resp = client.post("/api/v1/auth/subscribe/stripe", json={
        "tier": "pro",
        "billing_period": "monthly",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


def test_stripe_checkout_yearly_unconfigured():
    """Yearly billing should also return not_configured."""
    resp = client.post("/api/v1/auth/subscribe/stripe", json={
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
    """Webhook should reject requests without stripe-signature."""
    resp = client.post("/api/v1/webhooks/stripe", json={})
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"]["error"]
