"""Authentication and subscription management module.

Handles API key registration, tier subscriptions, and subscription expiry.
Uses in-memory storage. For production, migrate to a database (SQLite/PostgreSQL).
"""

import hashlib
import math
import secrets
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator

# --- Data Models ---

@dataclass
class Subscription:
    """Tracks a user's subscription state."""
    tier: str = "free"  # free, pro, enterprise
    period_start: float = 0.0  # Unix timestamp
    period_end: float = 0.0  # Unix timestamp
    auto_renew: bool = False
    polar_customer_id: str | None = None
    polar_subscription_id: str | None = None

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.tier == "free":
            return True  # Free tier never expires
        now = time.time()
        return self.period_end > now and self.period_start <= now

    def days_remaining(self) -> int:
        """Days until subscription expires. Returns large number for free tier."""
        if self.tier == "free":
            return 999_999
        now = time.time()
        remaining = self.period_end - now
        return max(0, math.ceil(remaining / 86400))


@dataclass
class User:
    """A registered API user."""
    email: str
    api_key_hash: str  # SHA-256 hash of the API key (never store raw key)
    api_key_prefix: str  # First 8 chars of the key for identification
    name: str = ""
    subscription: Subscription = field(default_factory=Subscription)
    created_at: float = field(default_factory=time.time)
    active: bool = True

    def check_period(self) -> None:
        """Check and handle subscription expiry. Auto-downgrade if needed."""
        sub = self.subscription
        if sub.tier != "free" and not sub.is_active:
            # Grace period: 7 days after expiry
            now = time.time()
            grace_end = sub.period_end + (7 * 86400)
            if now > grace_end:
                sub.tier = "free"
                sub.period_start = 0.0
                sub.period_end = 0.0
                sub.auto_renew = False


# --- Storage ---

class AuthStore:
    """In-memory auth store. Replace with database for production."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}  # api_key_hash -> User
        self._users_by_email: dict[str, User] = {}  # email -> User

    def create_user(self, email: str, name: str = "") -> str:
        """Register a new user and return the raw API key.

        The raw key is returned exactly once. Only the hash is stored.
        """
        if email.lower() in self._users_by_email:
            raise ValueError(f"Email already registered: {email}")

        raw_key = f"halal_{secrets.token_urlsafe(32)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:8]

        user = User(
            email=email.lower().strip(),
            api_key_hash=key_hash,
            api_key_prefix=key_prefix,
            name=name,
        )
        self._users[key_hash] = user
        self._users_by_email[user.email] = user
        return raw_key

    def get_user_by_key(self, raw_key: str) -> User | None:
        """Look up a user by their raw API key."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        user = self._users.get(key_hash)
        if user and user.active:
            user.check_period()  # Auto-expire if needed
            return user
        return None

    def get_user_by_hash(self, key_hash: str) -> User | None:
        """Look up a user by their API key hash (used by Polar webhooks)."""
        user = self._users.get(key_hash)
        if user:
            return user
        return None

    def get_user_by_email(self, email: str) -> User | None:
        """Look up a user by email."""
        user = self._users_by_email.get(email.lower().strip())
        if user and user.active:
            user.check_period()
            return user
        return None

    def revoke_key(self, raw_key: str) -> bool:
        """Revoke an API key by marking user as inactive."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        user = self._users.get(key_hash)
        if user:
            user.active = False
            # Also remove from email index so they can re-register
            self._users_by_email.pop(user.email, None)
            return True
        return False

    def regenerate_key(self, raw_key: str) -> str:
        """Generate a new API key for an existing user."""
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        user = self._users.get(key_hash)
        if not user or not user.active:
            raise ValueError("Invalid or inactive API key")

        new_raw_key = f"halal_{secrets.token_urlsafe(32)}"
        new_hash = hashlib.sha256(new_raw_key.encode()).hexdigest()
        new_prefix = new_raw_key[:8]

        # Remove old hash mapping
        del self._users[key_hash]
        # Add new mapping
        user.api_key_hash = new_hash
        user.api_key_prefix = new_prefix
        self._users[new_hash] = user

        return new_raw_key

    def subscribe(self, raw_key: str, tier: str, duration_days: int = 30) -> dict:
        """Manually upgrade a user's subscription tier."""
        if tier not in ("free", "pro", "enterprise"):
            raise ValueError(f"Unknown tier: {tier}")

        user = self.get_user_by_key(raw_key)
        if not user:
            raise ValueError("Invalid or inactive API key")

        now = time.time()
        user.subscription = Subscription(
            tier=tier,
            period_start=now,
            period_end=now + (duration_days * 86400),
            auto_renew=False,
        )

        return {
            "tier": tier,
            "period_start": user.subscription.period_start,
            "period_end": user.subscription.period_end,
            "days_remaining": user.subscription.days_remaining(),
        }

    def list_users(self) -> list[dict]:
        """List all registered users (admin use)."""
        result = []
        for user in self._users.values():
            user.check_period()
            result.append({
                "email": user.email,
                "name": user.name,
                "api_key_prefix": user.api_key_prefix,
                "tier": user.subscription.tier,
                "subscription_active": user.subscription.is_active,
                "days_remaining": user.subscription.days_remaining(),
                "active": user.active,
                "created_at": user.created_at,
            })
        return result


# Global auth store instance
auth_store = AuthStore()


# --- Pydantic Request/Response Models ---

class RegisterRequest(BaseModel):
    email: str = Field(..., description="Email address for the account")
    name: str = Field("", description="Display name (optional)")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v


class RegisterResponse(BaseModel):
    api_key: str = Field(..., description="Your API key. Save this - it won't be shown again!")
    api_key_prefix: str = Field(..., description="Key prefix for identification")
    email: str
    name: str
    tier: str = "free"
    message: str = "Store your API key securely. Pass it as X-API-Key header in all requests."


class SubscribeRequest(BaseModel):
    tier: str = Field(..., description="Target tier: free, pro, or enterprise")
    duration_days: int = Field(30, description="Subscription duration in days")


class SubscribeResponse(BaseModel):
    tier: str
    period_start: float
    period_end: float
    days_remaining: int
    message: str


class RevokeResponse(BaseModel):
    revoked: bool
    message: str


class KeyInfo(BaseModel):
    api_key_prefix: str
    email: str
    name: str
    tier: str
    subscription_active: bool
    days_remaining: int
    created_at: float


class KeysResponse(BaseModel):
    keys: list[KeyInfo]
    count: int


class PolarSubscribeRequest(BaseModel):
    """Polar checkout request."""
    tier: str = Field("pro", description="Target tier (only 'pro' available via Polar)")
    billing_period: str = Field("monthly", description="monthly or yearly")


class PolarSubscribeResponse(BaseModel):
    message: str
    checkout_url: str | None = None
    session_id: str | None = None
    status: str = "success"  # "success" | "not_configured" | "error"


class PolarPortalResponse(BaseModel):
    message: str
    portal_url: str | None = None
    status: str
