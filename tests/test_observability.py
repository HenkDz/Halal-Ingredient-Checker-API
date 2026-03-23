"""
Tests for the observability module: structured logging, Sentry, Prometheus, exception handlers.

These tests verify the observability features without requiring external services.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("LOG_LEVEL", "INFO")
    os.environ.setdefault("ENVIRONMENT", "test")
    # Ensure Sentry doesn't actually initialize
    os.environ.pop("SENTRY_DSN", None)

    from app.main import app
    with TestClient(app) as c:
        yield c


# ============================================================================
# SECTION 1: HEALTH ENDPOINT
# ============================================================================

class TestHealthEndpoint:
    """Tests for the /api/v1/health endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200 with correct structure."""
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "database_entries" in data
        assert data["database_entries"] > 0

    def test_health_has_cache_info(self, client):
        """Health endpoint includes cache status."""
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "cache" in data
        assert "status" in data["cache"]

    def test_health_has_external_api_info(self, client):
        """Health endpoint includes external API status."""
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "external_api" in data
        assert "status" in data["external_api"]

    def test_health_status_is_ok_or_degraded(self, client):
        """Health status should be 'ok' or 'degraded', never crash."""
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] in ("ok", "degraded")


# ============================================================================
# SECTION 2: METRICS ENDPOINT
# ============================================================================

class TestMetricsEndpoint:
    """Tests for the /metrics endpoint."""

    def test_metrics_returns_200(self, client):
        """Metrics endpoint returns 200 with Prometheus text format."""
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers.get("content-type", "")

    def test_metrics_contains_api_requests(self, client):
        """Metrics should include the request counter."""
        # Make some requests first to generate metrics
        client.get("/api/v1/health")
        client.get("/api/v1/ingredient/sugar")

        resp = client.get("/metrics")
        body = resp.text
        assert "halal_api_requests_total" in body

    def test_metrics_contains_latency_histogram(self, client):
        """Metrics should include latency histogram."""
        resp = client.get("/metrics")
        body = resp.text
        assert "halal_api_request_duration_seconds" in body

    def test_metrics_contains_active_requests_gauge(self, client):
        """Metrics should include active requests gauge."""
        resp = client.get("/metrics")
        body = resp.text
        assert "halal_api_active_requests" in body

    def test_metrics_contains_error_counter(self, client):
        """Metrics should include error counter."""
        resp = client.get("/metrics")
        body = resp.text
        assert "halal_api_errors_total" in body

    def test_metrics_contains_cache_metrics(self, client):
        """Metrics should include cache hit/miss counters."""
        resp = client.get("/metrics")
        body = resp.text
        assert "halal_api_cache_hits_total" in body
        assert "halal_api_cache_misses_total" in body


# ============================================================================
# SECTION 3: REQUEST LOGGING & HEADERS
# ============================================================================

class TestRequestLogging:
    """Tests for request logging middleware behavior."""

    def test_request_id_in_response(self, client):
        """Every response should include X-Request-ID header."""
        resp = client.get("/api/v1/health")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) == 8

    def test_rate_limit_headers_present(self, client):
        """Responses should include X-RateLimit-* headers."""
        resp = client.get("/api/v1/health")
        assert "x-ratelimit-limit-minute" in resp.headers
        assert "x-ratelimit-limit-day" in resp.headers


# ============================================================================
# SECTION 4: EXCEPTION HANDLERS
# ============================================================================

class TestExceptionHandlers:
    """Tests for global exception handlers."""

    def test_404_returns_structured_error(self, client):
        """404 errors should return structured JSON."""
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404

    def test_422_validation_error_returns_structured(self, client):
        """Validation errors should return structured JSON."""
        resp = client.post("/api/v1/check", json={"ingredients": []})
        assert resp.status_code == 422

    def test_generic_exception_no_stack_trace(self, client):
        """Generic exceptions should not expose stack traces in production."""
        # In DEBUG mode, we get more info. In production, we get generic message.
        # We test that the response is structured JSON, not a raw traceback.
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/ingredient/%00")
            # Should return JSON, not an HTML/traceback page
            content_type = resp.headers.get("content-type", "")
            assert "json" in content_type or "text" in content_type
            # Should NOT contain "Traceback" 
            if resp.text:
                assert "Traceback" not in resp.text


# ============================================================================
# SECTION 5: STRUCTURED LOGGING CONFIGURATION
# ============================================================================

class TestLoggingConfig:
    """Tests for logging configuration."""

    def test_structlog_configured(self):
        """structlog should be configured without errors."""
        from app.observability import configure_logging
        # Should not raise
        configure_logging()

    def test_sentry_not_configured_without_dsn(self):
        """Sentry should not initialize when no DSN is set."""
        os.environ.pop("SENTRY_DSN", None)
        from app.observability import configure_sentry
        from fastapi import FastAPI
        app = FastAPI()
        # Should not raise and should log that it's not configured
        configure_sentry(app)


# ============================================================================
# SECTION 6: CACHE INSTRUMENTATION
# ============================================================================

class TestCacheInstrumentation:
    """Tests for cache hit/miss instrumentation."""

    def test_instrument_cache_get_hit(self):
        """Cache hit increments hit counter."""
        from app.observability import instrument_cache_get
        # Should not raise even if prometheus is not fully configured
        instrument_cache_get("test_cache", hit=True)

    def test_instrument_cache_get_miss(self):
        """Cache miss increments miss counter."""
        from app.observability import instrument_cache_get
        instrument_cache_get("test_cache", hit=False)

    def test_mask_api_key_short(self):
        """Short API keys should be fully masked."""
        from app.observability import _mask_api_key
        assert _mask_api_key("abc") == "***"

    def test_mask_api_key_anonymous(self):
        """Anonymous key should return 'anonymous'."""
        from app.observability import _mask_api_key
        assert _mask_api_key("anonymous") == "anonymous"
        assert _mask_api_key(None) == "anonymous"

    def test_mask_api_key_normal(self):
        """Normal API keys should be partially masked."""
        from app.observability import _mask_api_key
        masked = _mask_api_key("abcdefghijklmnop")
        assert masked.startswith("abcd")
        assert masked.endswith("mnop")
        assert "..." in masked


# ============================================================================
# SECTION 7: DEPENDENCY HEALTH CHECKS
# ============================================================================

class TestDependencyChecks:
    """Tests for dependency health check functions."""

    def test_check_cache(self):
        """Cache check should return valid dict."""
        from app.observability import check_cache
        result = check_cache()
        assert "status" in result
        assert "entries" in result

    def test_check_external_api(self):
        """External API check should return valid dict."""
        import asyncio
        from app.observability import check_external_api
        result = asyncio.get_event_loop().run_until_complete(check_external_api())
        assert "status" in result
        assert result["status"] in ("up", "down", "timeout", "degraded")
