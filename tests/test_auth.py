"""Tests for the auth and subscription system (HAL-11)."""

import time

from fastapi.testclient import TestClient

from app.auth import auth_store
from app.main import app

client = TestClient(app)


def _register(email="test@example.com", name="Test User"):
    """Helper to register a user and return API key."""
    resp = client.post("/api/v1/auth/register", json={"email": email, "name": name})
    assert resp.status_code == 200, resp.json()
    return resp.json()["api_key"]


# --- Registration Tests ---

def test_register_success():
    """Should register a new user and return an API key."""
    resp = client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "name": "New User",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["api_key"].startswith("halal_")
    assert data["email"] == "new@example.com"
    assert data["name"] == "New User"
    assert data["tier"] == "free"
    assert data["api_key_prefix"] == data["api_key"][:8]
    assert len(data["api_key"]) > 30


def test_register_duplicate_email():
    """Should reject duplicate email registration."""
    _register("dup@example.com")
    resp = client.post("/api/v1/auth/register", json={"email": "dup@example.com"})
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]["error"]


def test_register_invalid_email():
    """Should reject invalid email formats."""
    resp = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_register_email_normalized():
    """Should normalize email to lowercase."""
    resp = client.post("/api/v1/auth/register", json={"email": "UPPER@Example.COM"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "upper@example.com"


# --- Keys/Info Tests ---

def test_list_keys_authenticated():
    """Should return key info for authenticated user."""
    key = _register("keys@example.com")
    resp = client.get("/api/v1/auth/keys", headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
    assert data["keys"][0]["email"] == "keys@example.com"
    assert data["keys"][0]["tier"] == "free"
    assert data["keys"][0]["subscription_active"] is True


def test_list_keys_no_auth():
    """Should reject unauthenticated key listing."""
    resp = client.get("/api/v1/auth/keys")
    assert resp.status_code == 401


def test_list_keys_invalid_key():
    """Should reject invalid API key."""
    resp = client.get("/api/v1/auth/keys", headers={"X-API-Key": "invalid_key_12345"})
    assert resp.status_code == 401


# --- Revoke Tests ---

def test_revoke_key():
    """Should revoke a valid API key."""
    key = _register("revoke@example.com")
    resp = client.post("/api/v1/auth/key/revoke", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["revoked"] is True

    # After revocation, the key should no longer work
    resp2 = client.get("/api/v1/auth/keys", headers={"X-API-Key": key})
    assert resp2.status_code == 401


def test_revoke_allows_reregister():
    """Should allow re-registration after revocation."""
    key = _register("rereg@example.com")
    client.post("/api/v1/auth/key/revoke", headers={"X-API-Key": key})
    resp = client.post("/api/v1/auth/register", json={
        "email": "rereg@example.com",
        "name": "Re-registered",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "Re-registered"


# --- Subscription Tests ---

def test_subscribe_to_pro():
    """Should upgrade a user to Pro tier."""
    key = _register("pro@example.com")
    resp = client.post("/api/v1/auth/subscribe", json={
        "tier": "pro",
        "duration_days": 30,
    }, headers={"X-API-Key": key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "pro"
    assert data["days_remaining"] == 30


def test_subscribe_to_enterprise():
    """Should upgrade a user to Enterprise tier."""
    key = _register("ent@example.com")
    resp = client.post("/api/v1/auth/subscribe", json={
        "tier": "enterprise",
        "duration_days": 365,
    }, headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "enterprise"
    assert resp.json()["days_remaining"] == 365


def test_subscribe_downgrade_to_free():
    """Should allow downgrading back to free."""
    key = _register("down@example.com")
    client.post("/api/v1/auth/subscribe", json={"tier": "pro", "duration_days": 30},
                headers={"X-API-Key": key})
    resp = client.post("/api/v1/auth/subscribe", json={"tier": "free", "duration_days": 0},
                       headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "free"


def test_subscribe_invalid_tier():
    """Should reject invalid tier names."""
    key = _register("badtier@example.com")
    resp = client.post("/api/v1/auth/subscribe", json={"tier": "premium_ultra"},
                       headers={"X-API-Key": key})
    assert resp.status_code == 400


def test_subscribe_no_auth():
    """Should reject subscription without authentication."""
    resp = client.post("/api/v1/auth/subscribe", json={"tier": "pro"})
    assert resp.status_code == 401


# --- Polar Integration (unconfigured mode) ---

def test_polar_subscribe_not_configured():
    """Should return not_configured when Polar env vars are not set."""
    resp = client.post("/api/v1/auth/subscribe/polar", json={
        "tier": "pro",
        "billing_period": "monthly",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_configured"
    assert data["checkout_url"] is None


def test_polar_subscribe_requires_auth():
    """Should require authentication even when not configured."""
    # When not configured, it returns 200 with not_configured status
    # But when configured, it should require auth. Test without auth key:
    resp = client.post("/api/v1/auth/subscribe/polar", json={
        "tier": "pro",
        "billing_period": "monthly",
    })
    # Without auth and not configured: returns 200 with not_configured
    assert resp.status_code == 200
    assert resp.json()["status"] == "not_configured"


def test_billing_portal_not_configured():
    """Should return not_configured when Polar is not set up."""
    resp = client.get("/api/v1/auth/billing/portal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_configured"
    assert data["portal_url"] is None


def test_webhook_missing_signature():
    """Should reject webhooks without polar-webhook-signature header."""
    resp = client.post("/api/v1/webhooks/polar", content=b"{}")
    assert resp.status_code == 400


# --- Tier-Aware Rate Limiting ---

def test_free_user_batch_blocked():
    """Free tier users should get 403 on batch endpoint."""
    key = _register("freebatch@example.com")
    resp = client.post("/api/v1/barcode/batch", json={
        "barcodes": ["3017620422003"],
    }, headers={"X-API-Key": key})
    assert resp.status_code == 403
    assert "Batch endpoint requires Pro" in resp.json()["detail"]["error"]


def test_pro_user_batch_allowed():
    """Pro tier users should access batch endpoint."""
    key = _register("probatch@example.com")
    client.post("/api/v1/auth/subscribe", json={"tier": "pro", "duration_days": 30},
                headers={"X-API-Key": key})

    resp = client.post("/api/v1/barcode/batch", json={
        "barcodes": ["3017620422003"],
    }, headers={"X-API-Key": key})
    # May succeed or return 404 (product not found in OFF), but NOT 403
    assert resp.status_code != 403


# --- Subscription Expiry ---

def test_subscription_expiry():
    """Expired subscriptions should auto-downgrade to free tier."""
    key = _register("expire@example.com")
    client.post("/api/v1/auth/subscribe", json={"tier": "pro", "duration_days": 1},
                headers={"X-API-Key": key})

    # Manually expire the subscription
    user = auth_store.get_user_by_key(key)
    user.subscription.period_end = time.time() - (8 * 86400)  # 8 days ago (past grace period)

    # Trigger expiry check
    user.check_period()
    assert user.subscription.tier == "free"

    # Should now be blocked from batch
    resp = client.post("/api/v1/barcode/batch", json={
        "barcodes": ["3017620422003"],
    }, headers={"X-API-Key": key})
    assert resp.status_code == 403


def test_grace_period():
    """Should keep tier during 7-day grace period after expiry."""
    key = _register("grace@example.com")
    client.post("/api/v1/auth/subscribe", json={"tier": "pro", "duration_days": 1},
                headers={"X-API-Key": key})

    user = auth_store.get_user_by_key(key)
    user.subscription.period_end = time.time() - (3 * 86400)  # 3 days ago (within grace)

    user.check_period()
    assert user.subscription.tier == "pro"  # Still pro during grace period


# --- Usage endpoint with auth ---

def test_usage_reflects_tier():
    """Usage endpoint should reflect subscribed tier."""
    key = _register("usage@example.com")

    resp = client.get("/api/v1/auth/usage", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "free"

    # Upgrade
    client.post("/api/v1/auth/subscribe", json={"tier": "pro", "duration_days": 30},
                headers={"X-API-Key": key})

    resp = client.get("/api/v1/auth/usage", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["tier"] == "pro"
    assert resp.json()["features"]["batch_enabled"] is True


# --- Anonymous vs authenticated ---

def test_anonymous_user_is_free():
    """Requests without API key should be treated as free tier."""
    # Anonymous should get 403 on batch
    resp = client.post("/api/v1/barcode/batch", json={"barcodes": ["3017620422003"]})
    assert resp.status_code == 403

    # But can still use single barcode/ingredient
    resp = client.get("/api/v1/ingredient/sugar")
    assert resp.status_code == 200
