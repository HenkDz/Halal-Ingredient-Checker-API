"""Shared test fixtures for all test modules."""

import pytest

from app.auth import auth_store
from app.ratelimit import rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the rate limiter before every test to prevent cross-test interference."""
    rate_limiter._usage.clear()
    rate_limiter._api_key_tiers.clear()
    yield
    rate_limiter._usage.clear()
    rate_limiter._api_key_tiers.clear()


@pytest.fixture(autouse=True)
def reset_auth_store():
    """Reset the auth store before every test."""
    auth_store._users.clear()
    auth_store._users_by_email.clear()
    yield
    auth_store._users.clear()
    auth_store._users_by_email.clear()


@pytest.fixture(autouse=True)
def clear_barcode_cache():
    """Clear OFF/assessment cache so failover tests see mocked HTTP, not stale data."""
    from app.barcode import _cache

    _cache.clear()
    yield
    _cache.clear()
