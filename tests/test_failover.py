"""
Failover and resilience testing for external API dependencies.

Tests what happens when:
1. Open Food Facts API is completely unreachable
2. OFF API returns 5xx errors
3. OFF API returns malformed data
4. OFF API is extremely slow (timeouts)
5. Network errors mid-request
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestOFFFailover:
    """
    Test graceful degradation when the Open Food Facts API is unavailable.
    These tests ensure the Halal Check API remains responsive even when
    external dependencies fail.
    """

    # --- Health endpoint should NEVER depend on OFF ---

    def test_health_endpoint_works_when_off_is_down(self):
        """Health endpoint must work regardless of OFF API status."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            # Simulate OFF being completely down
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            # Health endpoint checks OFF status; "degraded" is correct when OFF is down
            assert data["status"] in ("ok", "degraded")

    # --- Barcode endpoint graceful degradation ---

    def test_barcode_returns_502_when_off_unreachable(self):
        """Barcode endpoint should return 502 (Bad Gateway) when OFF is down."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/barcode/3017620422003")
            # Should be 502 (Bad Gateway) — external API error
            assert response.status_code == 502
            data = response.json()
            assert "error" in data["detail"] or "error" in data

    def test_barcode_returns_502_when_off_returns_500(self):
        """Barcode endpoint should handle OFF returning server errors."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"error": "Internal Server Error"}
            mock_response.raise_for_status.side_effect = Exception("500 Server Error")
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/barcode/3017620422003")
            assert response.status_code == 502

    def test_barcode_handles_off_timeout_gracefully(self):
        """Barcode endpoint should handle OFF timeout without hanging."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=TimeoutError("Request timed out"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/barcode/3068320113005")
            # Should not hang — should return an error
            assert response.status_code in (502, 504)

    def test_barcode_handles_malformed_off_response(self):
        """Barcode endpoint should handle malformed OFF data gracefully."""
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock:
            # OFF returns a product with completely broken data
            mock.return_value = {
                "product_name": 12345,  # Wrong type
                "brands": {"broken": "structure"},
                "labels_tags": "not a list",
            }

            # Should not crash — should return some result or error
            response = client.get("/api/v1/barcode/9999999999")
            # Either succeeds with degraded data or returns an error (400 validation, 502 gateway)
            assert response.status_code in (200, 400, 502)

    # --- Batch barcode failover ---

    def test_batch_barcode_partial_failure(self):
        """Batch endpoint should return partial results when some barcodes fail."""
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock:
            # First call succeeds, second fails, third succeeds
            mock.side_effect = [
                {
                    "product_name": "Good Product",
                    "brands": "Test",
                    "ingredients_text_en": "sugar, water",
                    "labels_tags": [],
                },
                Exception("OFF API down for this barcode"),
                {
                    "product_name": "Another Good Product",
                    "brands": "Test",
                    "ingredients_text_en": "salt, olive oil",
                    "labels_tags": [],
                },
            ]

            # Register a pro user first
            register_resp = client.post(
                "/api/v1/auth/register",
                json={"email": "batch_failover@test.com", "name": "Test User"},
            )
            api_key = register_resp.json()["api_key"]

            # Subscribe to pro for batch access
            client.post(
                "/api/v1/auth/subscribe",
                json={"tier": "pro", "duration_days": 30},
                headers={"X-API-Key": api_key},
            )

            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["1111111111", "2222222222", "3333333333"]},
                headers={"X-API-Key": api_key},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert data["failed"] >= 1
            assert data["successful"] >= 1

    def test_batch_barcode_all_fail(self):
        """Batch endpoint should return all errors when OFF is completely down."""
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("OFF API completely down")

            register_resp = client.post(
                "/api/v1/auth/register",
                json={"email": "batch_all_fail@test.com", "name": "Test User"},
            )
            api_key = register_resp.json()["api_key"]

            client.post(
                "/api/v1/auth/subscribe",
                json={"tier": "pro", "duration_days": 30},
                headers={"X-API-Key": api_key},
            )

            # Use unique barcodes
            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["9988776655443", "9988776655444"]},
                headers={"X-API-Key": api_key},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["failed"] == 2
            assert data["successful"] == 0

    # --- Ingredient check should NEVER depend on OFF ---

    def test_ingredient_check_works_when_off_is_down(self):
        """Direct ingredient checking must work without OFF."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("OFF is down"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            # Direct ingredient check should still work
            response = client.post(
                "/api/v1/check",
                json={"ingredients": ["gelatin", "sugar", "olive oil"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert data["haram"] == 1  # gelatin

    def test_single_ingredient_lookup_works_when_off_is_down(self):
        """Single ingredient lookup must work without OFF."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("OFF is down"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/ingredient/gelatin")
            assert response.status_code == 200
            assert response.json()["verdict"] == "haram"

    # --- Product search should NEVER depend on OFF ---

    def test_product_search_works_when_off_is_down(self):
        """Product search uses local DB, should work without OFF."""
        with patch("app.barcode.httpx.AsyncClient") as mock_client:
            mock_instance = MagicMock()
            mock_instance.get = AsyncMock(side_effect=Exception("OFF is down"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            response = client.get("/api/v1/products/search?q=sugar&limit=5")
            assert response.status_code == 200

    # --- Concurrent failure resilience ---

    @pytest.mark.asyncio
    async def test_concurrent_barcode_requests_with_off_flaky(self):
        """Multiple concurrent requests with flaky OFF should not cause cascading failures."""
        import asyncio
        from unittest.mock import patch

        call_count = 0

        async def flaky_off(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # Every other call fails
            if call_count % 2 == 0:
                raise Exception("OFF intermittent error")
            return {
                "product_name": f"Product {call_count}",
                "brands": "Test",
                "ingredients_text_en": "sugar, water",
                "labels_tags": [],
            }

        from app.barcode import assess_barcode

        with patch("app.barcode.fetch_product_from_off", side_effect=flaky_off):
            results = await asyncio.gather(
                *[assess_barcode(f"100000000{i}") for i in range(6)],
                return_exceptions=True,
            )

        # At least some should succeed, none should be unhandled exceptions
        successes = [r for r in results if not isinstance(r, Exception)]
        assert len(successes) >= 2, f"Too many failures: {len(results) - len(successes)} out of {len(results)}"
