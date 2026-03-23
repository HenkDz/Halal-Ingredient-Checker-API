"""Stripe payment integration module.

Handles checkout sessions, webhook processing, and billing portal management.

Configuration via environment variables:
    STRIPE_SECRET_KEY       - Stripe secret API key
    STRIPE_PUBLISHABLE_KEY  - Stripe publishable key (returned to frontend)
    STRIPE_WEBHOOK_SECRET   - Stripe webhook signing secret
    STRIPE_PRO_MONTHLY_PRICE_ID   - Price ID for Pro monthly ($9/mo)
    STRIPE_PRO_YEARLY_PRICE_ID    - Price ID for Pro yearly ($79/yr)
    STRIPE_SUCCESS_URL      - URL to redirect after successful checkout
    STRIPE_CANCEL_URL       - URL to redirect if user cancels checkout
"""

import os
import logging
from typing import Optional

import stripe

logger = logging.getLogger(__name__)

# --- Configuration ---

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_MONTHLY_PRICE_ID = os.getenv("STRIPE_PRO_MONTHLY_PRICE_ID", "")
STRIPE_PRO_YEARLY_PRICE_ID = os.getenv("STRIPE_PRO_YEARLY_PRICE_ID", "")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://halalcheck.example.com/success")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://halalcheck.example.com/cancel")

# Grace period for failed payments (seconds)
GRACE_PERIOD_SECONDS = 7 * 86400  # 7 days

# Tier mapping from Stripe price IDs
PRICE_TO_TIER: dict[str, str] = {}
# Populated at init time from env vars
if STRIPE_PRO_MONTHLY_PRICE_ID:
    PRICE_TO_TIER[STRIPE_PRO_MONTHLY_PRICE_ID] = "pro"
if STRIPE_PRO_YEARLY_PRICE_ID:
    PRICE_TO_TIER[STRIPE_PRO_YEARLY_PRICE_ID] = "pro"


def is_configured() -> bool:
    """Check if Stripe is properly configured with required keys."""
    return bool(
        STRIPE_SECRET_KEY
        and STRIPE_PUBLISHABLE_KEY
        and STRIPE_WEBHOOK_SECRET
        and (STRIPE_PRO_MONTHLY_PRICE_ID or STRIPE_PRO_YEARLY_PRICE_ID)
    )


def init_stripe() -> None:
    """Initialize the Stripe client with the secret key."""
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY


# Auto-initialize on module import
init_stripe()


# --- Checkout Session ---

def create_checkout_session(
    user_email: str,
    api_key: str,
    tier: str = "pro",
    billing_period: str = "monthly",
) -> dict:
    """Create a Stripe Checkout Session for subscription.

    Args:
        user_email: Customer's email address.
        api_key: User's API key (stored as metadata for webhook lookup).
        tier: Target subscription tier (currently only 'pro').
        billing_period: 'monthly' or 'yearly'.

    Returns:
        Dict with 'checkout_url' and 'session_id'.

    Raises:
        ValueError: If Stripe is not configured or parameters are invalid.
        stripe.StripeError: On Stripe API errors.
    """
    # Validate inputs first (before checking Stripe config)
    if tier != "pro":
        raise ValueError(f"Only 'pro' tier is available via Stripe checkout. Got: {tier}")

    if billing_period not in ("monthly", "yearly"):
        raise ValueError(f"billing_period must be 'monthly' or 'yearly'. Got: {billing_period}")

    if not is_configured():
        raise ValueError(
            "Stripe is not configured. Set the required environment variables "
            "(STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET, "
            "STRIPE_PRO_MONTHLY_PRICE_ID or STRIPE_PRO_YEARLY_PRICE_ID)."
        )

    if billing_period == "monthly":
        price_id = STRIPE_PRO_MONTHLY_PRICE_ID
    elif billing_period == "yearly":
        price_id = STRIPE_PRO_YEARLY_PRICE_ID

    if not price_id:
        raise ValueError(
            f"No Stripe price ID configured for {billing_period} billing. "
            f"Set STRIPE_PRO_MONTHLY_PRICE_ID or STRIPE_PRO_YEARLY_PRICE_ID."
        )

    # Create or retrieve Stripe customer
    customer = stripe.Customer.create(
        email=user_email,
        metadata={"api_key_hash": _hash_key(api_key)},
    )

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer=customer.id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=STRIPE_CANCEL_URL,
        metadata={
            "tier": tier,
            "billing_period": billing_period,
        },
        subscription_data={
            "metadata": {
                "tier": tier,
                "api_key_hash": _hash_key(api_key),
            },
            "trial_period_days": None,  # No trial by default
        },
    )

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "customer_id": customer.id,
    }


# --- Billing Portal ---

def create_billing_portal_session(customer_id: str) -> dict:
    """Create a Stripe Billing Portal session for managing subscription.

    Args:
        customer_id: The Stripe customer ID.

    Returns:
        Dict with 'portal_url'.

    Raises:
        ValueError: If Stripe is not configured.
        stripe.StripeError: On Stripe API errors.
    """
    if not is_configured():
        raise ValueError("Stripe is not configured.")

    if not customer_id:
        raise ValueError("No Stripe customer ID on record. Subscribe first.")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=STRIPE_SUCCESS_URL,
    )

    return {
        "portal_url": session.url,
    }


# --- Webhook Processing ---

def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """Verify and parse a Stripe webhook event.

    Args:
        payload: Raw request body bytes.
        sig_header: Value of the Stripe-Signature header.

    Returns:
        Parsed Stripe event dict.

    Raises:
        ValueError: If signature verification fails or Stripe is not configured.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError("STRIPE_WEBHOOK_SECRET is not configured.")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        # stripe.error.SignatureVerificationError or generic error
        error_msg = str(e).lower()
        if "signature" in error_msg:
            logger.warning("Stripe webhook signature verification failed: %s", e)
            raise ValueError("Invalid webhook signature") from e
        raise

    return event


def process_webhook_event(event: dict) -> dict:
    """Process a verified Stripe webhook event and return actions to apply.

    Returns a dict describing what the caller should do:
        {
            "event_type": "checkout.session.completed" | "customer.subscription.deleted" | "invoice.payment_failed",
            "api_key_hash": "...",
            "tier": "pro" | None,
            "stripe_customer_id": "...",
            "stripe_subscription_id": "...",
            "action": "activate" | "cancel" | "grant_grace" | "ignore",
            "period_start": timestamp | None,
            "period_end": timestamp | None,
        }
    """
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    result: dict = {
        "event_type": event_type,
        "api_key_hash": None,
        "tier": None,
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "action": "ignore",
        "period_start": None,
        "period_end": None,
    }

    if event_type == "checkout.session.completed":
        # New subscription created via checkout
        api_key_hash = data.get("metadata", {}).get("api_key_hash")
        tier = data.get("metadata", {}).get("tier", "pro")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")

        if not api_key_hash:
            logger.warning("checkout.session.completed missing api_key_hash metadata")
            result["action"] = "ignore"
            return result

        # Fetch the subscription to get period dates
        sub = None
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
            except stripe.StripeError as e:
                logger.error("Failed to fetch subscription %s: %s", subscription_id, e)

        result.update({
            "api_key_hash": api_key_hash,
            "tier": tier,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "action": "activate",
            "period_start": sub["current_period_start"] if sub else None,
            "period_end": sub["current_period_end"] if sub else None,
        })

    elif event_type == "customer.subscription.deleted":
        # Subscription cancelled/expired
        subscription_id = data.get("id")
        customer_id = data.get("customer")
        api_key_hash = data.get("metadata", {}).get("api_key_hash")

        result.update({
            "api_key_hash": api_key_hash,
            "tier": None,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "action": "cancel",
        })

    elif event_type == "invoice.payment_failed":
        # Payment failed - start grace period
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")
        api_key_hash = None

        # Try to get api_key_hash from subscription metadata
        if subscription_id:
            try:
                sub = stripe.Subscription.retrieve(subscription_id)
                api_key_hash = sub.get("metadata", {}).get("api_key_hash")
            except stripe.StripeError as e:
                logger.error("Failed to fetch subscription %s: %s", subscription_id, e)

        result.update({
            "api_key_hash": api_key_hash,
            "tier": None,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "action": "grant_grace",
            "period_end": data.get("period_end"),
        })

    elif event_type == "customer.subscription.updated":
        # Subscription changed (e.g., renewal, plan change)
        subscription_id = data.get("id")
        customer_id = data.get("customer")
        api_key_hash = data.get("metadata", {}).get("api_key_hash")
        status = data.get("status")

        if status == "active":
            # Renewal or reactivation
            result.update({
                "api_key_hash": api_key_hash,
                "tier": data.get("metadata", {}).get("tier", "pro"),
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "action": "activate",
                "period_start": data.get("current_period_start"),
                "period_end": data.get("current_period_end"),
            })
        else:
            result["action"] = "ignore"

    else:
        logger.info("Ignoring unhandled Stripe event type: %s", event_type)

    return result


def apply_webhook_action(auth_store_obj, action_result: dict) -> None:
    """Apply a webhook action to the auth store.

    Finds the user by api_key_hash and updates their subscription.
    """
    action = action_result.get("action", "ignore")
    api_key_hash = action_result.get("api_key_hash")

    if action == "ignore" or not api_key_hash:
        return

    user = auth_store_obj.get_user_by_hash(api_key_hash)
    if not user:
        logger.warning(
            "Webhook action %s: no user found for api_key_hash=%s",
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
        user.subscription.auto_renew = True
        user.subscription.stripe_customer_id = action_result.get("stripe_customer_id")
        user.subscription.stripe_subscription_id = action_result.get("stripe_subscription_id")
        user.active = True

        logger.info(
            "Activated %s subscription for user %s (ends: %s)",
            tier,
            user.email,
            user.subscription.period_end,
        )

    elif action == "cancel":
        user.subscription.tier = "free"
        user.subscription.period_start = 0.0
        user.subscription.period_end = 0.0
        user.subscription.auto_renew = False
        user.subscription.stripe_customer_id = None
        user.subscription.stripe_subscription_id = None

        logger.info("Cancelled subscription for user %s", user.email)

    elif action == "grant_grace":
        # Extend period_end by grace period from now
        import time
        user.subscription.period_end = time.time() + GRACE_PERIOD_SECONDS

        logger.info(
            "Granted 7-day grace period for user %s (until %s)",
            user.email,
            user.subscription.period_end,
        )


# --- Utility ---

def _hash_key(api_key: str) -> str:
    """Hash an API key using SHA-256 (same as auth store)."""
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()
