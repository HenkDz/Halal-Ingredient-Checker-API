"""Rate limiting module with tier-based quotas.

Uses an in-memory sliding window counter. Suitable for single-instance
deployment. For multi-instance, replace with Redis-backed slowapi.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitTier:
    """Defines rate limits for a subscription tier."""
    name: str
    daily_limit: int
    per_minute_limit: int
    batch_enabled: bool = True
    max_batch_size: int = 50
    detailed_results: bool = False


# Tier definitions
TIERS = {
    "free": RateLimitTier(
        name="free",
        daily_limit=100,
        per_minute_limit=10,
        batch_enabled=False,
        max_batch_size=0,
        detailed_results=False,
    ),
    "pro": RateLimitTier(
        name="pro",
        per_minute_limit=100,
        daily_limit=10_000,
        batch_enabled=True,
        max_batch_size=50,
        detailed_results=True,
    ),
    "enterprise": RateLimitTier(
        name="enterprise",
        per_minute_limit=500,
        daily_limit=1_000_000,
        batch_enabled=True,
        max_batch_size=200,
        detailed_results=True,
    ),
}


@dataclass
class UsageRecord:
    """Tracks usage for a single API key within a time window."""
    timestamps_per_minute: list[float] = field(default_factory=list)
    timestamps_daily: list[float] = field(default_factory=list)


class RateLimiter:
    """In-memory sliding window rate limiter with tier support."""

    def __init__(self) -> None:
        self._usage: dict[str, UsageRecord] = defaultdict(UsageRecord)
        self._api_key_tiers: dict[str, str] = {}

    # --- Tier management ---

    def set_tier(self, api_key: str, tier: str) -> None:
        """Assign a tier to an API key."""
        if tier not in TIERS:
            raise ValueError(f"Unknown tier: {tier}. Must be one of: {list(TIERS.keys())}")
        self._api_key_tiers[api_key] = tier

    def get_tier(self, api_key: str) -> RateLimitTier:
        """Get the tier for an API key. Defaults to 'free'."""
        tier_name = self._api_key_tiers.get(api_key, "free")
        return TIERS[tier_name]

    # --- Rate checking ---

    def check_rate_limit(
        self, api_key: str, cost: int = 1
    ) -> tuple[bool, dict]:
        """Check if a request is allowed under rate limits.

        Returns:
            (allowed, headers_dict)
            headers_dict contains X-RateLimit-* headers for the response.

        Args:
            api_key: Identifier for the client.
            cost: How many requests this operation costs (batch = N).
        """
        now = time.time()
        one_minute_ago = now - 60
        one_day_ago = now - 86400

        tier = self.get_tier(api_key)
        record = self._usage[api_key]

        # Prune old entries (sliding window)
        record.timestamps_per_minute = [
            t for t in record.timestamps_per_minute if t > one_minute_ago
        ]
        record.timestamps_daily = [
            t for t in record.timestamps_daily if t > one_day_ago
        ]

        minute_count = len(record.timestamps_per_minute)
        daily_count = len(record.timestamps_daily)

        # Build headers
        headers = {
            "X-RateLimit-Limit-Minute": str(tier.per_minute_limit),
            "X-RateLimit-Remaining-Minute": str(max(0, tier.per_minute_limit - minute_count)),
            "X-RateLimit-Limit-Day": str(tier.daily_limit),
            "X-RateLimit-Remaining-Day": str(max(0, tier.daily_limit - daily_count)),
            "X-RateLimit-Tier": tier.name,
        }

        # Check limits
        if minute_count + cost > tier.per_minute_limit:
            headers["Retry-After"] = str(int(record.timestamps_per_minute[0] - one_minute_ago + 1))
            return False, headers

        if daily_count + cost > tier.daily_limit:
            # Reset at midnight
            headers["Retry-After"] = str(int(record.timestamps_daily[0] - one_day_ago + 1))
            return False, headers

        return True, headers

    def record_request(self, api_key: str, cost: int = 1) -> None:
        """Record that a request was made (after checking it passes)."""
        now = time.time()
        record = self._usage[api_key]
        for _ in range(cost):
            record.timestamps_per_minute.append(now)
            record.timestamps_daily.append(now)

    # --- Usage stats ---

    def get_usage(self, api_key: str) -> dict:
        """Get current usage statistics for an API key."""
        now = time.time()
        one_minute_ago = now - 60
        one_day_ago = now - 86400

        tier = self.get_tier(api_key)
        record = self._usage[api_key]

        minute_count = sum(1 for t in record.timestamps_per_minute if t > one_minute_ago)
        daily_count = sum(1 for t in record.timestamps_daily if t > one_day_ago)

        return {
            "tier": tier.name,
            "current_period": {
                "minute": {
                    "used": minute_count,
                    "limit": tier.per_minute_limit,
                    "remaining": max(0, tier.per_minute_limit - minute_count),
                },
                "day": {
                    "used": daily_count,
                    "limit": tier.daily_limit,
                    "remaining": max(0, tier.daily_limit - daily_count),
                },
            },
            "features": {
                "batch_enabled": tier.batch_enabled,
                "max_batch_size": tier.max_batch_size,
                "detailed_results": tier.detailed_results,
            },
        }

    def reset_usage(self, api_key: str) -> None:
        """Reset usage for an API key (useful for testing)."""
        self._usage.pop(api_key, None)


# Global rate limiter instance
rate_limiter = RateLimiter()
