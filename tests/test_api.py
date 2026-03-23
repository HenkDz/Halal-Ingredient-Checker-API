"""Tests for Halal Check API - Phase 1"""

import pytest
from fastapi.testclient import TestClient

# Import the ingredient data functions
from data.ingredients import lookup_ingredient, check_ingredients, INGREDIENTS
from app.main import app

client = TestClient(app)


# ============ DATA LAYER TESTS ============

class TestIngredientLookup:
    """Tests for the ingredient lookup function."""

    def test_lookup_haram_ingredient_gelatin(self):
        result = lookup_ingredient("gelatin")
        assert result is not None
        assert result["verdict"] == "haram"
        assert "gelatin" in result["name"].lower()

    def test_lookup_haram_ingredient_alcohol(self):
        result = lookup_ingredient("alcohol")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_haram_ingredient_lard(self):
        result = lookup_ingredient("lard")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_haram_ingredient_pork(self):
        result = lookup_ingredient("pork")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_haram_ingredient_carmine(self):
        result = lookup_ingredient("carmine")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_haram_e_number_120(self):
        result = lookup_ingredient("E120")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_haram_e_number_441(self):
        result = lookup_ingredient("e441")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_halal_ingredient_water(self):
        result = lookup_ingredient("water")
        assert result is not None
        assert result["verdict"] == "halal"

    def test_lookup_halal_ingredient_sugar(self):
        result = lookup_ingredient("sugar")
        assert result is not None
        assert result["verdict"] == "halal"

    def test_lookup_halal_ingredient_olive_oil(self):
        result = lookup_ingredient("olive oil")
        assert result is not None
        assert result["verdict"] == "halal"

    def test_lookup_doubtful_ingredient_rennet(self):
        result = lookup_ingredient("rennet")
        assert result is not None
        assert result["verdict"] == "doubtful"

    def test_lookup_doubtful_e471(self):
        result = lookup_ingredient("e471")
        assert result is not None
        assert result["verdict"] == "doubtful"

    def test_lookup_by_alternative_name_gelatine(self):
        result = lookup_ingredient("gelatine")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_by_alternative_name_ethanol(self):
        result = lookup_ingredient("ethanol")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_case_insensitive(self):
        result = lookup_ingredient("GELATIN")
        assert result is not None
        assert result["verdict"] == "haram"

    def test_lookup_unknown_ingredient(self):
        result = lookup_ingredient("xyznonexistent")
        assert result is None

    def test_database_has_minimum_entries(self):
        """Ensure we have a reasonable number of ingredients."""
        assert len(INGREDIENTS) >= 20


class TestCheckIngredients:
    """Tests for the bulk check function."""

    def test_check_all_halal(self):
        results = check_ingredients(["water", "sugar", "salt", "olive oil"])
        assert len(results) == 4
        assert all(r["verdict"] == "halal" for r in results)

    def test_check_contains_haram(self):
        results = check_ingredients(["water", "gelatin", "sugar"])
        assert len(results) == 3
        verdicts = {r["verdict"] for r in results}
        assert "haram" in verdicts

    def test_check_mixed_verdicts(self):
        results = check_ingredients(["olive oil", "gelatin", "E471", "water"])
        assert len(results) == 4
        verdicts = {r["verdict"] for r in results}
        assert "halal" in verdicts
        assert "haram" in verdicts
        assert "doubtful" in verdicts

    def test_check_unknown_ingredient(self):
        results = check_ingredients(["unknown_chemical_xyz"])
        assert len(results) == 1
        assert results[0]["verdict"] == "unknown"

    def test_check_empty_list(self):
        results = check_ingredients([])
        assert len(results) == 0

    def test_check_preserves_query(self):
        results = check_ingredients(["GELATIN"])
        assert results[0]["query"] == "GELATIN"
        assert results[0]["verdict"] == "haram"


# ============ API ENDPOINT TESTS ============

class TestHealthEndpoint:
    def test_health_check(self):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.4.0"
        assert data["database_entries"] > 0


class TestGetIngredientEndpoint:
    def test_get_known_haram_ingredient(self):
        response = client.get("/api/v1/ingredient/gelatin")
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "haram"
        assert data["name"] is not None
        assert data["reason"] is not None

    def test_get_known_halal_ingredient(self):
        response = client.get("/api/v1/ingredient/olive%20oil")
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "halal"

    def test_get_unknown_ingredient(self):
        response = client.get("/api/v1/ingredient/nonexistent_ingredient")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data["detail"]

    def test_get_by_e_number(self):
        response = client.get("/api/v1/ingredient/e120")
        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "haram"
        assert data["e_number"] == "E120"


class TestCheckEndpoint:
    def test_check_endpoint_basic(self):
        response = client.post(
            "/api/v1/check",
            json={"ingredients": ["water", "sugar", "olive oil"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["halal"] == 3
        assert data["haram"] == 0
        assert data["overall_verdict"] == "halal"
        assert len(data["results"]) == 3

    def test_check_endpoint_with_haram(self):
        response = client.post(
            "/api/v1/check",
            json={"ingredients": ["water", "gelatin", "alcohol"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["haram"] >= 1
        assert data["overall_verdict"] == "haram"

    def test_check_endpoint_doubtful(self):
        response = client.post(
            "/api/v1/check",
            json={"ingredients": ["water", "E471"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["doubtful"] >= 1
        assert data["overall_verdict"] == "doubtful"

    def test_check_endpoint_empty_body(self):
        response = client.post(
            "/api/v1/check",
            json={"ingredients": []},
        )
        # Should fail validation (min_length=1)
        assert response.status_code == 422

    def test_check_endpoint_no_body(self):
        response = client.post("/api/v1/check")
        assert response.status_code == 422

    def test_check_endpoint_large_list(self):
        ingredients = [f"ingredient_{i}" for i in range(50)]
        response = client.post(
            "/api/v1/check",
            json={"ingredients": ingredients},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
