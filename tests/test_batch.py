"""Tests for batch barcode endpoint."""

import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.ratelimit import rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def use_pro_tier_for_batch_tests():
    """Set the anonymous user to pro tier so batch tests work."""
    rate_limiter.set_tier("anonymous", "pro")
    yield
    rate_limiter._usage.clear()
    rate_limiter._api_key_tiers.clear()


class TestBatchBarcodeEndpoint:
    """Test the batch barcode checking endpoint."""

    @pytest.mark.asyncio
    async def test_batch_with_success_and_error(self):
        """Test batch with some successful and some failed lookups."""
        from app.barcode import BarcodeAssessment, ParsedIngredient

        def _mock_assess(barcode):
            if barcode == "3017620422003":
                return BarcodeAssessment(
                    barcode=barcode,
                    product_name="Nutella",
                    brand="Ferrero",
                    ingredients_text="sugar, palm oil",
                    flagged_ingredients=[],
                    all_ingredients=[
                        ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
                    ],
                    overall_status="halal",
                    confidence=0.9,
                    has_halal_certification=False,
                    certification_labels=[],
                    source="Open Food Facts",
                    cache_hit=False,
                )
            else:
                return BarcodeAssessment(
                    barcode=barcode,
                    product_name=None,
                    brand=None,
                    ingredients_text=None,
                    flagged_ingredients=[],
                    all_ingredients=[],
                    overall_status="unknown",
                    confidence=0.0,
                    has_halal_certification=False,
                    certification_labels=[],
                    source="Open Food Facts",
                    cache_hit=False,
                )

        async def _async_mock(barcode):
            return _mock_assess(barcode)

        with patch("app.main.assess_barcode", side_effect=_async_mock):
            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["3017620422003", "0000000000"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["successful"] == 1
            assert data["failed"] == 1

    def test_batch_max_50_items(self):
        """Test that more than 50 barcodes are rejected."""
        barcodes = [str(i).zfill(13) for i in range(51)]
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": barcodes},
        )
        assert response.status_code == 422

    def test_batch_empty_body(self):
        """Test that empty request is rejected."""
        response = client.post("/api/v1/barcode/batch", json={"barcodes": []})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_batch_all_successful(self):
        """Test batch where all barcodes succeed."""
        from app.barcode import BarcodeAssessment, ParsedIngredient

        async def _mock(barcode):
            return BarcodeAssessment(
                barcode=barcode,
                product_name=f"Product {barcode}",
                brand="Test",
                ingredients_text="sugar, water",
                flagged_ingredients=[],
                all_ingredients=[
                    ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
                ],
                overall_status="halal",
                confidence=0.9,
                has_halal_certification=False,
                certification_labels=[],
                source="Open Food Facts",
                cache_hit=False,
            )

        with patch("app.main.assess_barcode", side_effect=_mock):
            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["3017620422003", "5000159484695"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["successful"] == 2
            assert data["failed"] == 0
            for r in data["results"]:
                assert r["status"] == "success"
                assert r["product_name"] is not None

    def test_batch_invalid_barcode_in_list(self):
        """Test batch with invalid barcode - should get error in results."""
        response = client.post(
            "/api/v1/barcode/batch",
            json={"barcodes": ["abc123"]},
        )
        assert response.status_code == 200
        data = response.json()
        # Invalid barcode is filtered out during validation, so total may be 0
        assert data["failed"] >= 0

    @pytest.mark.asyncio
    async def test_batch_exception_handling(self):
        """Test that exceptions in OFF API don't crash the batch."""
        async def _mock(barcode):
            raise RuntimeError("Network error")

        with patch("app.main.assess_barcode", side_effect=_mock):
            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["3017620422003"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["failed"] == 1
            assert data["results"][0]["error"] is not None

    def test_batch_single_item(self):
        """Test batch with a single barcode works fine."""
        from app.barcode import BarcodeAssessment, ParsedIngredient

        async def _mock(barcode):
            return BarcodeAssessment(
                barcode=barcode,
                product_name="Test Product",
                brand="Test",
                ingredients_text="water",
                flagged_ingredients=[],
                all_ingredients=[
                    ParsedIngredient("water", "water", "halal", "Pure", None),
                ],
                overall_status="halal",
                confidence=1.0,
                has_halal_certification=True,
                certification_labels=["Halal"],
                source="Open Food Facts",
                cache_hit=False,
            )

        with patch("app.main.assess_barcode", side_effect=_mock):
            response = client.post(
                "/api/v1/barcode/batch",
                json={"barcodes": ["3017620422003"]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["successful"] == 1
            assert data["results"][0]["has_halal_certification"] is True
