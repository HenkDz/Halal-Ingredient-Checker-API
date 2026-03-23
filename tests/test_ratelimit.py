"""Tests for Halal Check API - Phase 4: Rate Limiting"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ratelimit import rate_limiter, TIERS


client = TestClient(app)


# ============ RATE LIMIT HEADERS ON ALL RESPONSES ============

class TestRateLimitHeaders:
    """Every API response should include X-RateLimit-* headers."""

    def test_health_has_rate_limit_headers(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers
        assert "X-RateLimit-Limit-Day" in response.headers
        assert "X-RateLimit-Remaining-Day" in response.headers
        assert "X-RateLimit-Tier" in response.headers
        assert response.headers["X-RateLimit-Tier"] == "free"

    def test_ingredient_lookup_has_rate_limit_headers(self):
        response = client.get("/api/v1/ingredient/gelatin")
        assert response.status_code == 200
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Tier" in response.headers

    def test_check_endpoint_has_rate_limit_headers(self):
        response = client.post(
            "/api/v1/check",
            json={"ingredients": ["water", "sugar"]},
        )
        assert response.status_code == 200
        assert "X-RateLimit-Limit-Minute" in response.headers

    def test_api_key_identifies_client(self):
        """Different API keys should have independent rate limits."""
        resp1 = client.get("/api/v1/health", headers={"X-API-Key": "key-1"})
        resp2 = client.get("/api/v1/health", headers={"X-API-Key": "key-2"})
        assert resp1.headers["X-RateLimit-Remaining-Minute"] == resp2.headers["X-RateLimit-Remaining-Minute"]

    def test_api_key_via_query_param(self):
        response = client.get("/api/v1/health?api_key=test-key")
        assert response.status_code == 200
        assert "X-RateLimit-Tier" in response.headers


# ============ FREE TIER RATE LIMITING ============

class TestFreeTierRateLimiting:
    """Test that free tier (default) is rate limited."""

    def test_free_tier_minute_limit(self):
        """Free tier: 10 requests per minute. Should get 429 on the 11th."""
        # Free tier limit is 10/min. Use 11 requests.
        for i in range(10):
            response = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "free-ratelimit-test"})
            assert response.status_code == 200, f"Request {i+1} should succeed"

        # 11th should be rate limited
        response = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "free-ratelimit-test"})
        assert response.status_code == 429
        data = response.json()
        assert data["detail"]["error"] == "Rate limit exceeded"
        assert "Retry-After" in response.headers

    def test_rate_limit_429_includes_limit_info(self):
        """429 response should include tier and limit details."""
        # Exhaust the minute limit
        for i in range(10):
            client.get("/api/v1/ingredient/water", headers={"X-API-Key": "free-info-test"})

        response = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "free-info-test"})
        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["tier"] == "free"
        assert "limits" in detail
        assert "retry_after" in detail

    def test_health_endpoint_not_rate_limited(self):
        """Health endpoint should never be rate limited."""
        for i in range(15):
            response = client.get("/api/v1/health", headers={"X-API-Key": "health-test"})
            assert response.status_code == 200, f"Health request {i+1} should always succeed"

    def test_usage_endpoint_not_rate_limited(self):
        """Usage endpoint should not count against rate limit."""
        for i in range(15):
            response = client.get("/api/v1/auth/usage", headers={"X-API-Key": "usage-test"})
            assert response.status_code == 200


# ============ PRO TIER ============

class TestProTierRateLimiting:
    """Test pro tier has higher limits."""

    def test_pro_tier_higher_limits(self):
        """Pro tier should have 100 requests/minute."""
        rate_limiter.set_tier("pro-key", "pro")

        for i in range(11):
            response = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "pro-key"})
            assert response.status_code == 200, f"Pro request {i+1} should succeed"

        assert response.headers["X-RateLimit-Tier"] == "pro"
        assert response.headers["X-RateLimit-Limit-Minute"] == "100"

    def test_pro_tier_remaining_decreases(self):
        """Remaining count should decrease with each request."""
        rate_limiter.set_tier("pro-count", "pro")

        resp1 = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "pro-count"})
        resp2 = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "pro-count"})

        remaining1 = int(resp1.headers["X-RateLimit-Remaining-Minute"])
        remaining2 = int(resp2.headers["X-RateLimit-Remaining-Minute"])
        assert remaining2 == remaining1 - 1


# ============ ENTERPRISE TIER ============

class TestEnterpriseTier:
    """Test enterprise tier."""

    def test_enterprise_tier_limits(self):
        rate_limiter.set_tier("ent-key", "enterprise")
        response = client.get("/api/v1/ingredient/water", headers={"X-API-Key": "ent-key"})
        assert response.headers["X-RateLimit-Tier"] == "enterprise"
        assert response.headers["X-RateLimit-Limit-Minute"] == "500"
        assert response.headers["X-RateLimit-Limit-Day"] == "1000000"


# ============ BATCH ENDPOINT TIER RESTRICTION ============

class TestBatchTierRestriction:
    """Batch endpoint should be restricted to Pro and Enterprise tiers."""

    def test_free_tier_batch_returns_403(self):
        """Free tier should get 403 on batch endpoint."""
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": ["3017620422003"]},
            headers={"X-API-Key": "free-batch-user"},
        )
        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "Batch endpoint requires Pro or Enterprise tier"
        assert data["detail"]["current_tier"] == "free"

    def test_pro_tier_batch_allowed(self):
        """Pro tier should be able to access batch endpoint."""
        rate_limiter.set_tier("pro-batch-user", "pro")
        # We can't test actual barcode lookup (needs network), but we can
        # verify the tier check passes by trying with invalid barcodes
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": ["invalid"]},
            headers={"X-API-Key": "pro-batch-user"},
        )
        # Should not be 403 (tier check passes). Will be 200 with errors for invalid barcodes.
        assert response.status_code != 403

    def test_enterprise_tier_larger_batch(self):
        """Enterprise tier allows up to 200 barcodes per batch."""
        rate_limiter.set_tier("ent-batch-user", "enterprise")
        barcodes = ["3017620422003"] * 50  # 50 valid barcodes (may fail on network but tier check passes)
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": barcodes},
            headers={"X-API-Key": "ent-batch-user"},
        )
        # Should not be 400 for batch size (enterprise allows 200)
        # Could be 200 or 429 but not 400 for batch size or 403 for tier
        assert response.status_code not in (400, 403)

    def test_pro_tier_batch_size_limit(self):
        """Pro tier should reject batches larger than 50."""
        rate_limiter.set_tier("pro-oversize", "pro")
        barcodes = ["3017620422003"] * 51
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": barcodes},
            headers={"X-API-Key": "pro-oversize"},
        )
        # Either 400 (our tier check) or 422 (Pydantic max_length=50 validation)
        assert response.status_code in (400, 422)


# ============ USAGE TRACKING ENDPOINT ============

class TestUsageEndpoint:
    """Test the /api/v1/auth/usage endpoint."""

    def test_usage_returns_tier_info(self):
        response = client.get("/api/v1/auth/usage", headers={"X-API-Key": "usage-info"})
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "free"
        assert "current_period" in data
        assert "minute" in data["current_period"]
        assert "day" in data["current_period"]
        assert "features" in data

    def test_usage_shows_correct_tier(self):
        rate_limiter.set_tier("pro-usage", "pro")
        response = client.get("/api/v1/auth/usage", headers={"X-API-Key": "pro-usage"})
        assert response.status_code == 200
        data = response.json()
        assert data["tier"] == "pro"
        assert data["features"]["batch_enabled"] is True
        assert data["features"]["max_batch_size"] == 50

    def test_usage_shows_consumption(self):
        """Usage should increase after requests."""
        api_key = "consumption-test"
        # Make 3 requests
        for _ in range(3):
            client.get("/api/v1/ingredient/water", headers={"X-API-Key": api_key})

        response = client.get("/api/v1/auth/usage", headers={"X-API-Key": api_key})
        assert response.status_code == 200
        data = response.json()
        assert data["current_period"]["minute"]["used"] >= 3
        assert data["current_period"]["day"]["used"] >= 3

    def test_usage_features_for_free_tier(self):
        response = client.get("/api/v1/auth/usage", headers={"X-API-Key": "free-features"})
        data = response.json()
        assert data["features"]["batch_enabled"] is False
        assert data["features"]["max_batch_size"] == 0
        assert data["features"]["detailed_results"] is False

    def test_usage_features_for_enterprise_tier(self):
        rate_limiter.set_tier("ent-features", "enterprise")
        response = client.get("/api/v1/auth/usage", headers={"X-API-Key": "ent-features"})
        data = response.json()
        assert data["features"]["batch_enabled"] is True
        assert data["features"]["max_batch_size"] == 200
        assert data["features"]["detailed_results"] is True


# ============ INDEPENDENT API KEY TRACKING ============

class TestIndependentRateLimiting:
    """Different API keys should have independent rate limits."""

    def test_different_keys_independent(self):
        """Exhausting one key's limit shouldn't affect another."""
        key1, key2 = "indep-key-1", "indep-key-2"

        # Exhaust key1's minute limit
        for _ in range(10):
            client.get("/api/v1/ingredient/water", headers={"X-API-Key": key1})

        # key1 should be rate limited
        resp = client.get("/api/v1/ingredient/water", headers={"X-API-Key": key1})
        assert resp.status_code == 429

        # key2 should still work
        resp = client.get("/api/v1/ingredient/water", headers={"X-API-Key": key2})
        assert resp.status_code == 200


# ============ BATCH COST CALCULATION ============

class TestBatchCost:
    """Batch endpoint should cost 1 request per barcode."""

    def test_batch_costs_per_barcode(self):
        """Each barcode in a batch should cost 1 request from the rate limit."""
        rate_limiter.set_tier("batch-cost-key", "pro")
        # Free tier has 10/min, pro has 100/min
        # Send a batch of 5 barcodes
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": ["invalid1", "invalid2", "invalid3", "invalid4", "invalid5"]},
            headers={"X-API-Key": "batch-cost-key"},
        )
        # Check usage after - should have used 3 (only 3 are not valid 8-14 digit format... 
        # actually "invalid1" etc. don't match \d{8,14} so cost=0)
        # Let me use valid format barcodes
        rate_limiter.reset_usage("batch-cost-key2")
        rate_limiter.set_tier("batch-cost-key2", "pro")
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": ["12345678", "12345679", "12345670"]},
            headers={"X-API-Key": "batch-cost-key2"},
        )
        # 3 valid barcodes = cost of 3
        usage = rate_limiter.get_usage("batch-cost-key2")
        assert usage["current_period"]["minute"]["used"] == 3
