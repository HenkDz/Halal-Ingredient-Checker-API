"""Tests for barcode lookup module."""

from unittest.mock import AsyncMock, patch

import pytest

from app.barcode import (
    ParsedIngredient,
    _compute_confidence,
    _detect_halal_certification,
    _parse_ingredients_string,
    _remove_percentages,
    _remove_qualifiers,
    assess_barcode,
)

# ============ INGREDIENT PARSING TESTS ============

class TestIngredientParsing:
    """Test the ingredient string parser."""

    def test_simple_comma_separated(self):
        text = "water, sugar, salt, olive oil"
        result = _parse_ingredients_string(text)
        assert "water" in result
        assert "sugar" in result
        assert "salt" in result
        assert "olive oil" in result
        assert len(result) == 4

    def test_parenthesized_sub_ingredients(self):
        text = "emulsifier (soy lecithin), water, sugar"
        result = _parse_ingredients_string(text)
        assert "emulsifier" in result
        assert "soy lecithin" in result
        assert "water" in result

    def test_nested_parentheses(self):
        text = "whey powder (milk), emulsifier (E471, E472), citric acid"
        result = _parse_ingredients_string(text)
        assert "whey powder" in result
        assert "milk" in result
        assert "emulsifier" in result
        assert "E471" in result
        assert "E472" in result
        assert "citric acid" in result

    def test_percentages_removed(self):
        text = "sugar 38%, cocoa 7.4%, hazelnuts 13%"
        result = _parse_ingredients_string(text)
        for item in result:
            assert "%" not in item

    def test_semicolon_separated(self):
        text = "water; sugar; salt"
        result = _parse_ingredients_string(text)
        assert "water" in result
        assert "sugar" in result
        assert "salt" in result

    def test_and_separator(self):
        text = "water, sugar and salt"
        result = _parse_ingredients_string(text)
        assert "water" in result
        assert "sugar" in result
        assert "salt" in result

    def test_empty_string(self):
        assert _parse_ingredients_string("") == []
        assert _parse_ingredients_string(None) == []

    def test_real_world_nutella_style(self):
        """Test parsing a Nutella-style French ingredient string."""
        text = "Sucre, huile de palme, NOISETTES 13%, cacao maigre 7,4%, LAIT écrémé en poudre 6,6%, LACTOSERUM en poudre, émulsifiants: lécithines (SOJA), vanilline"
        result = _parse_ingredients_string(text)
        assert len(result) > 0
        # Should extract at least the main ingredients
        assert any("sucre" in r.lower() or "sugar" in r.lower() for r in result)

    def test_qualifiers_removed(self):
        text = "organic sugar, natural vanilla extract, enriched flour"
        result = _parse_ingredients_string(text)
        # Qualifiers should be stripped
        for item in result:
            assert "organic" not in item.lower()
            assert "natural" not in item.lower()

    def test_trailing_periods_removed(self):
        text = "water, sugar, salt."
        result = _parse_ingredients_string(text)
        for item in result:
            assert not item.endswith(".")

    def test_slash_in_sub_ingredients(self):
        text = "emulsifier (mono/diglycerides), water"
        result = _parse_ingredients_string(text)
        assert "mono" in result
        assert "diglycerides" in result


class TestRemovePercentages:
    def test_simple_percentage(self):
        assert _remove_percentages("sugar 38%") == "sugar"

    def test_no_percentage(self):
        assert _remove_percentages("sugar") == "sugar"

    def test_complex(self):
        result = _remove_percentages("cocoa maigre 7,4%")
        assert "%" not in result


class TestRemoveQualifiers:
    def test_organic(self):
        result = _remove_qualifiers("organic sugar")
        assert "organic" not in result.lower()
        assert "sugar" in result.lower()

    def test_multiple_qualifiers(self):
        result = _remove_qualifiers("organic natural enriched flour")
        assert "organic" not in result.lower()
        assert "natural" not in result.lower()
        assert "enriched" not in result.lower()
        assert "flour" in result.lower()


class TestHalalCertification:
    def test_halal_in_labels_tags(self):
        product = {"labels_tags": ["en:halal", "en:vegetarian"]}
        has_cert, labels = _detect_halal_certification(product)
        assert has_cert is True
        assert len(labels) >= 1

    def test_no_halal_certification(self):
        product = {"labels_tags": ["en:vegetarian", "en:gluten-free"]}
        has_cert, labels = _detect_halal_certification(product)
        assert has_cert is False

    def test_halal_in_labels_text(self):
        product = {"labels": "Halal Certified", "labels_tags": []}
        has_cert, labels = _detect_halal_certification(product)
        assert has_cert is True

    def test_empty_product(self):
        has_cert, labels = _detect_halal_certification({})
        assert has_cert is False
        assert labels == []


class TestConfidenceScore:
    def test_all_known_halal(self):
        ingredients = [
            ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
            ParsedIngredient("water", "water", "halal", "Pure water", None),
        ]
        score = _compute_confidence(ingredients, has_certification=False)
        assert score > 0.8

    def test_with_certification(self):
        """Certification should boost confidence when there are some unknowns."""
        ingredients = [
            ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
            ParsedIngredient("xyz1", "xyz1", "unknown", "Not found", None),
        ]
        score_with_cert = _compute_confidence(ingredients, has_certification=True)
        score_without = _compute_confidence(ingredients, has_certification=False)
        assert score_with_cert > score_without

    def test_all_unknown(self):
        ingredients = [
            ParsedIngredient("xyz1", "xyz1", "unknown", "Not found", None),
            ParsedIngredient("xyz2", "xyz2", "unknown", "Not found", None),
        ]
        score = _compute_confidence(ingredients, has_certification=False)
        assert score < 0.3

    def test_empty_ingredients(self):
        score = _compute_confidence([], has_certification=False)
        assert score == 0.0

    def test_many_unknowns_penalty(self):
        ingredients = [
            ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
            ParsedIngredient("xyz1", "xyz1", "unknown", "Not found", None),
            ParsedIngredient("xyz2", "xyz2", "unknown", "Not found", None),
            ParsedIngredient("xyz3", "xyz3", "unknown", "Not found", None),
        ]
        score = _compute_confidence(ingredients, has_certification=False)
        # Should have a penalty for high unknown ratio
        assert score < 0.5


# ============ BARCODE ASSESSMENT TESTS ============

class TestBarcodeAssessment:
    """Test the full barcode assessment flow."""

    @pytest.mark.asyncio
    async def test_product_not_found(self):
        """404 case: barcode not in OFF database."""
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            assessment = await assess_barcode("0000000000")
            assert assessment.overall_status == "unknown"
            assert assessment.product_name is None
            assert assessment.confidence == 0.0

    @pytest.mark.asyncio
    async def test_product_with_halal_ingredients(self):
        """Test a product where all ingredients are halal."""
        mock_product = {
            "product_name": "Pure Olive Oil",
            "brands": "Test Brand",
            "ingredients_text_en": "olive oil, salt",
            "labels_tags": [],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567890")
            assert assessment.product_name == "Pure Olive Oil"
            assert assessment.overall_status == "halal"
            assert len(assessment.all_ingredients) == 2
            assert len(assessment.flagged_ingredients) == 0
            assert assessment.confidence > 0.5

    @pytest.mark.asyncio
    async def test_product_with_haram_ingredients(self):
        """Test a product containing haram ingredients."""
        mock_product = {
            "product_name": "Gummy Bears",
            "brands": "Haribo",
            "ingredients_text_en": "sugar, glucose syrup, gelatin, citric acid",
            "labels_tags": [],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567891")
            assert assessment.overall_status == "haram"
            assert len(assessment.flagged_ingredients) > 0
            flagged_names = [f["name"] for f in assessment.flagged_ingredients]
            assert "gelatin" in flagged_names

    @pytest.mark.asyncio
    async def test_product_with_halal_certification(self):
        """Test a product with halal certification."""
        mock_product = {
            "product_name": "Halal Chicken",
            "brands": "Halal Foods Inc",
            "ingredients_text_en": "chicken, salt, water",
            "labels_tags": ["en:halal", "en:organic"],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567892")
            assert assessment.has_halal_certification is True
            assert assessment.overall_status == "halal"

    @pytest.mark.asyncio
    async def test_product_with_doubtful_ingredients(self):
        """Test a product with doubtful ingredients like E471."""
        mock_product = {
            "product_name": "Chocolate Bar",
            "brands": "Test Co",
            "ingredients_text_en": "sugar, cocoa butter, E471, vanilla extract",
            "labels_tags": [],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567893")
            assert assessment.overall_status == "doubtful"
            assert len(assessment.flagged_ingredients) > 0

    @pytest.mark.asyncio
    async def test_invalid_barcode_format(self):
        """Test that invalid barcode raises ValueError."""
        with pytest.raises(ValueError):
            await assess_barcode("abc123")

    @pytest.mark.asyncio
    async def test_product_no_ingredients(self):
        """Test a product with no ingredients listed."""
        mock_product = {
            "product_name": "Unknown Product",
            "brands": "Test",
            "ingredients_text_en": "",
            "labels_tags": [],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567894")
            assert assessment.overall_status == "unknown"
            assert len(assessment.all_ingredients) == 0

    @pytest.mark.asyncio
    async def test_french_ingredients_fallback(self):
        """Test that non-English ingredient text still gets parsed."""
        mock_product = {
            "product_name": "Produit Francais",
            "brands": "Test",
            "ingredients_text": "sucre, eau, sel",
            "labels_tags": [],
        }
        with patch("app.barcode.fetch_product_from_off", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_product
            assessment = await assess_barcode("1234567895")
            assert len(assessment.all_ingredients) == 3


# ============ API ENDPOINT TESTS ============

class TestBarcodeEndpoint:
    """Test the barcode API endpoint."""

    @pytest.mark.asyncio
    async def test_barcode_not_found_returns_404(self):
        """Test that unknown barcode returns 404."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        with patch("app.main.assess_barcode", new_callable=AsyncMock) as mock_assess:
            from app.barcode import BarcodeAssessment
            mock_assess.return_value = BarcodeAssessment(
                barcode="0000000000",
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
            response = client.get("/api/v1/barcode/0000000000")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_barcode_success(self):
        """Test successful barcode lookup."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        with patch("app.main.assess_barcode", new_callable=AsyncMock) as mock_assess:
            from app.barcode import BarcodeAssessment, ParsedIngredient
            mock_assess.return_value = BarcodeAssessment(
                barcode="3017620422003",
                product_name="Nutella",
                brand="Ferrero",
                ingredients_text="sugar, palm oil, hazelnuts",
                flagged_ingredients=[],
                all_ingredients=[
                    ParsedIngredient("sugar", "sugar", "halal", "Plant-based", None),
                    ParsedIngredient("palm oil", "palm oil", "halal", "Plant-based", None),
                ],
                overall_status="halal",
                confidence=0.85,
                has_halal_certification=False,
                certification_labels=[],
                source="Open Food Facts",
                cache_hit=False,
            )
            response = client.get("/api/v1/barcode/3017620422003")
            assert response.status_code == 200
            data = response.json()
            assert data["product_name"] == "Nutella"
            assert data["overall_status"] == "halal"
            assert data["confidence"] == 0.85
            assert data["ingredient_count"] == 2

    def test_invalid_barcode_format_returns_400(self):
        """Test that invalid barcode format returns 400."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.get("/api/v1/barcode/abc123")
        assert response.status_code == 400
