"""Polar.sh payment integration module.

Handles checkout sessions, webhook processing, and customer portal management.

Replaces the previous Stripe integration (app/stripe.py).

Configuration via environment variables:
    POLAR_ACCESS_TOKEN       - Polar organization access token
    POLAR_WEBHOOK_SECRET     - Polar webhook signing secret (base64-encoded)
    POLAR_PRO_MONTHLY_PRODUCT_ID   - Product ID for Pro monthly ($9/mo)
    POLAR_PRO_YEARLY_PRODUCT_ID    - Product ID for Pro yearly ($79/yr)
    POLAR_SUCCESS_URL        - URL to redirect after successful checkout
    POLAR_CANCEL_URL         - URL to redirect if user cancels checkout
"""

import os
import hashlib
import hmac
import base64
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Union

import httpx

logger = logging.getLogger(__name__)

# --- Configuration ---

POLAR_ACCESS_TOKEN = os.getenv("POLAR_ACCESS_TOKEN", "")
POLAR_WEBHOOK_SECRET = os.getenv("POLAR_WEBHOOK_SECRET", "")
POLAR_PRO_MONTHLY_PRODUCT_ID = os.getenv("POLAR_PRO_MONTHLY_PRODUCT_ID", "")
POLAR_PRO_YEARLY_PRODUCT_ID = os.getenv("POLAR_PRO_YEARLY_PRODUCT_ID", "")
POLAR_SUCCESS_URL = os.getenv("POLAR_SUCCESS_URL", "https://halalcheck.example.com/success")
POLAR_CANCEL_URL = os.getenv("POLAR_CANCEL_URL", "https://halalcheck.example.com/cancel")

# Polar API base URL
POLAR_SERVER_ENV = os.getenv("POLAR_SERVER_ENV", "production")  # "production" or "sandbox"

# Grace period for failed payments (seconds)
GRACE_PERIOD_SECONDS = 7 * 86400  # 7 days


def _get_api_base() -> str:
    """Return the Polar API base URL based on environment."""
    if POLAR_SERVER_ENV == "sandbox":
        return "https://sandbox-api.polar.sh"
    return "https://api.polar.sh"


def is_configured() -> bool:
    """Check if Polar is properly configured with required keys."""
    return bool(
        POLAR_ACCESS_TOKEN
        and POLAR_WEBHOOK_SECRET
        and (POLAR_PRO_MONTHLY_PRODUCT_ID or POLAR_PRO_YEARLY_PRODUCT_ID)
    )


def _get_http_client() -> httpx.Client:
    """Create an httpx client for Polar API calls."""
    return httpx.Client(
        base_url=_get_api_base(),
        headers={
            "Authorization": f"Bearer {POLAR_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# --- Checkout Session ---

def create_checkout_session(
    user_email: str,
    api_key: str,
    tier: str = "pro",
    billing_period: str = "monthly",
) -> dict:
    """Create a Polar Checkout Session for subscription.

    Args:
        user_email: Customer's email address.
        api_key: User's API key (stored as metadata for webhook lookup).
        tier: Target subscription tier (currently only 'pro').
        billing_period: 'monthly' or 'yearly'.

    Returns:
        Dict with 'checkout_url' and 'session_id'.

    Raises:
        ValueError: If Polar is not configured or parameters are invalid.
        httpx.HTTPStatusError: On Polar API errors.
    """
    if tier != "pro":
        raise ValueError(f"Only 'pro' tier is available via Polar checkout. Got: {tier}")

    if billing_period not in ("monthly", "yearly"):
        raise ValueError(f"billing_period must be 'monthly' or 'yearly'. Got: {billing_period}")

    if not is_configured():
        raise ValueError(
            "Polar is not configured. Set the required environment variables "
            "(POLAR_ACCESS_TOKEN, POLAR_WEBHOOK_SECRET, "
            "POLAR_PRO_MONTHLY_PRODUCT_ID or POLAR_PRO_YEARLY_PRODUCT_ID)."
        )

    if billing_period == "monthly":
        product_id = POLAR_PRO_MONTHLY_PRODUCT_ID
    else:
        product_id = POLAR_PRO_YEARLY_PRODUCT_ID

    if not product_id:
        raise ValueError(
            f"No Polar product ID configured for {billing_period} billing. "
            f"Set POLAR_PRO_MONTHLY_PRODUCT_ID or POLAR_PRO_YEARLY_PRODUCT_ID."
        )

    payload = {
        "products": [product_id],
        "success_url": POLAR_SUCCESS_URL + "?checkout_id={CHECKOUT_ID}",
        "return_url": POLAR_CANCEL_URL,
        "customer_email": user_email,
        "metadata": {
            "tier": tier,
            "billing_period": billing_period,
            "api_key_hash": _hash_key(api_key),
        },
    }

    with _get_http_client() as client:
        response = client.post("/v1/checkouts/", json=payload)
        response.raise_for_status()
        data = response.json()

    return {
        "checkout_url": data["url"],
        "session_id": data["id"],
        "customer_id": data.get("customer_id"),
    }


# --- Customer Portal ---

def create_billing_portal_session(customer_id: str) -> dict:
    """Create a Polar Customer Portal session for managing subscription.

    Args:
        customer_id: The Polar customer ID.

    Returns:
        Dict with 'portal_url'.

    Raises:
        ValueError: If Polar is not configured or customer_id is missing.
        httpx.HTTPStatusError: On Polar API errors.
    """
    if not is_configured():
        raise ValueError("Polar is not configured.")

    if not customer_id:
        raise ValueError("No Polar customer ID on record. Subscribe first.")

    with _get_http_client() as client:
        response = client.post(
            "/v1/customer-portal/sessions/",
            json={"customer_id": customer_id},
        )
        response.raise_for_status()
        data = response.json()

    return {
        "portal_url": data.get("url", ""),
    }


# --- Webhook Processing ---

def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify and parse a Polar webhook event.

    Polar uses the Standard Webhooks specification.
    The signature header is "Polar-Webhook-Signature" with format: t=<timestamp>,v1=<signature>
    The webhook secret must be base64-decoded before use.

    Args:
        payload: Raw request body bytes.
        sig_header: Value of the Polar-Webhook-Signature header.

    Returns:
        Parsed webhook event dict.

    Raises:
        ValueError: If signature verification fails or Polar is not configured.
    """
    if not POLAR_WEBHOOK_SECRET:
        raise ValueError("POLAR_WEBHOOK_SECRET is not configured.")

    try:
        # Parse the signature header: t=<timestamp>,v1=<signature>
        parts = {}
        for item in sig_header.split(","):
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()

        timestamp = parts.get("t", "")
        signature = parts.get("v1", "")

        if not timestamp or not signature:
            raise ValueError("Missing timestamp or signature in webhook header")

        # Check timestamp freshness (reject events older than 5 minutes)
        try:
            event_ts = int(timestamp)
        except ValueError:
            raise ValueError("Invalid timestamp in webhook header")

        now = int(time.time())
        if abs(now - event_ts) > 300:
            raise ValueError("Webhook timestamp too old (possible replay attack)")

        # Decode the base64 secret
        try:
            secret = base64.b64decode(POLAR_WEBHOOK_SECRET)
        except Exception:
            secret = POLAR_WEBHOOK_SECRET.encode()

        # Build the signed payload: timestamp.raw_payload
        signed_payload = f"{timestamp}.".encode() + payload

        # Compute HMAC-SHA256
        expected_sig = hmac.new(secret, signed_payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid webhook signature")

        # Parse the JSON payload
        event = json.loads(payload)

    except json.JSONDecodeError as e:
        logger.error("Failed to parse webhook payload as JSON: %s", e)
        raise ValueError("Invalid webhook payload") from e
    except (AttributeError, ValueError) as e:
        error_msg = str(e).lower()
        if "signature" in error_msg or "timestamp" in error_msg:
            logger.warning("Polar webhook signature verification failed: %s", e)
            raise ValueError("Invalid webhook signature") from e
        raise

    return event


def process_webhook_event(event: dict) -> dict:
    """Process a verified Polar webhook event and return actions to apply.

    Returns a dict describing what the caller should do.
    """
    event_type = event.get("type", {})
    data = event.get("data", {})

    result: dict = {
        "event_type": event_type,
        "api_key_hash": None,
        "tier": None,
        "polar_customer_id": None,
        "polar_subscription_id": None,
        "action": "ignore",
        "period_start": None,
        "period_end": None,
    }

    # Extract metadata from subscription or customer
    metadata = data.get("metadata", {})
    customer_id = data.get("customer_id")
    subscription_id = data.get("id")

    api_key_hash = metadata.get("api_key_hash")
    tier = metadata.get("tier", "pro")

    if event_type in ("subscription.created", "subscription.active"):
        if not api_key_hash:
            result["action"] = "ignore"
            return result

        result.update({
            "api_key_hash": api_key_hash,
            "tier": tier,
            "polar_customer_id": customer_id,
            "polar_subscription_id": subscription_id,
            "action": "activate",
            "period_start": _parse_timestamp(data.get("started_at")),
            "period_end": _parse_timestamp(data.get("current_period_end")),
        })

    elif event_type == "subscription.canceled":
        cancel_at_period_end = data.get("cancel_at_period_end", False)
        if cancel_at_period_end:
            result["action"] = "ignore"
        else:
            result.update({
                "api_key_hash": api_key_hash,
                "tier": None,
                "polar_customer_id": customer_id,
                "polar_subscription_id": subscription_id,
                "action": "cancel",
            })

    elif event_type == "subscription.revoked":
        result.update({
            "api_key_hash": api_key_hash,
            "tier": None,
            "polar_customer_id": customer_id,
            "polar_subscription_id": subscription_id,
            "action": "cancel",
        })

    elif event_type == "subscription.past_due":
        result.update({
            "api_key_hash": api_key_hash,
            "tier": None,
            "polar_customer_id": customer_id,
            "polar_subscription_id": subscription_id,
            "action": "grant_grace",
            "period_end": _parse_timestamp(data.get("current_period_end")),
        })

    elif event_type == "subscription.updated":
        status = data.get("status")
        if status == "active" and api_key_hash:
            result.update({
                "api_key_hash": api_key_hash,
                "tier": tier,
                "polar_customer_id": customer_id,
                "polar_subscription_id": subscription_id,
                "action": "activate",
                "period_start": _parse_timestamp(data.get("started_at")),
                "period_end": _parse_timestamp(data.get("current_period_end")),
            })
        else:
            result["action"] = "ignore"

    else:
        logger.info("Ignoring unhandled Polar event type: %s", event_type)

    return result


def apply_webhook_action(auth_store_obj, action_result: dict) -> None:
    """Apply a webhook action to the auth store."""
    action = action_result.get("action", "ignore")
    api_key_hash = action_result.get("api_key_hash")

    if action == "ignore" or not api_key_hash:
        return

    user = auth_store_obj.get_user_by_hash(api_key_hash)
    if not user:
        logger.warning(
            "Webhook action %s: no user found for api_key_hash=%s...",
            action,
            api_key_hash[:12] + "...",
        )
        return

    if action == "activate":
        tier = action_result.get("tier", "pro")
        period_start = action_result.get("period_start")
        period_end = action_result.get("period_end")

        user.subscription.tier = tier
        if period_start:
            user.subscription.period_start = float(period_start)
        if period_end:
            user.subscription.period_end = float(period_end)
        if not user.subscription.period_end:
            user.subscription.period_end = time.time() + 30 * 86400
        user.subscription.auto_renew = True
        user.subscription.polar_customer_id = action_result.get("polar_customer_id")
        user.subscription.polar_subscription_id = action_result.get("polar_subscription_id")
        user.active = True

        logger.info(
            "Activated %s subscription for user %s (ends: %s)",
            tier, user.email, user.subscription.period_end,
        )

    elif action == "cancel":
        user.subscription.tier = "free"
        user.subscription.period_start = 0.0
        user.subscription.period_end = 0.0
        user.subscription.auto_renew = False
        user.subscription.polar_customer_id = None
        user.subscription.polar_subscription_id = None
        logger.info("Cancelled subscription for user %s", user.email)

    elif action == "grant_grace":
        user.subscription.period_end = time.time() + GRACE_PERIOD_SECONDS
        logger.info(
            "Granted 7-day grace period for user %s (until %s)",
            user.email, user.subscription.period_end,
        )


# --- Utility ---

def _hash_key(api_key: str) -> str:
    """Hash an API key using SHA-256 (same as auth store)."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def _parse_timestamp(value) -> Optional[float]:
    """Parse a timestamp from various formats (ISO string, int, float, None)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.timestamp()
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None
    return None
