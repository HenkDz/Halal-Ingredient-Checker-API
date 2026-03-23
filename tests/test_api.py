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
        assert data["version"] == "0.5.0"
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


# ============ PRODUCTS DATABASE TESTS (Phase 2.5) ============

class TestProductSearch:
    """Tests for the product search functionality."""

    def test_search_by_brand(self):
        from data.products import search_products
        result = search_products("Nutella")
        assert result["total"] > 0
        assert len(result["results"]) > 0
        assert any("nutella" in r["name"].lower() for r in result["results"])

    def test_search_by_product_name(self):
        from data.products import search_products
        result = search_products("chocolate")
        assert result["total"] > 0

    def test_search_by_barcode(self):
        from data.products import search_products
        result = search_products("3017620422003")
        assert result["total"] >= 1
        assert result["results"][0]["name"] == "Nutella 200g"

    def test_search_no_results(self):
        from data.products import search_products
        result = search_products("zzznonexistentzzz")
        assert result["total"] == 0
        assert result["results"] == []

    def test_search_pagination(self):
        from data.products import search_products
        result = search_products("Coca-Cola", limit=3, offset=0)
        assert len(result["results"]) <= 3
        assert result["limit"] == 3

    def test_get_product_by_barcode_found(self):
        from data.products import get_product_by_barcode
        product = get_product_by_barcode("3017620422003")
        assert product is not None
        assert product["name"] == "Nutella 200g"
        assert product["halal_status"] == "halal"
        assert product["brand"] == "Nestle"

    def test_get_product_by_barcode_not_found(self):
        from data.products import get_product_by_barcode
        product = get_product_by_barcode("9999999999999")
        assert product is None

    def test_product_database_size(self):
        from data.products import get_products_count
        count = get_products_count()
        assert count >= 1000, f"Expected at least 1000 products, got {count}"

    def test_product_brand_stats(self):
        from data.products import get_brand_stats
        stats = get_brand_stats()
        assert stats["total_products"] >= 1000
        assert stats["total_brands"] >= 5
        assert "halal" in stats["verdicts"]
        assert "haram" in stats["verdicts"]
        assert stats["verdicts"]["halal"] > stats["verdicts"]["haram"]

    def test_products_have_required_fields(self):
        from data.products import search_products
        result = search_products("KitKat", limit=5)
        for product in result["results"]:
            assert "barcode" in product
            assert "brand" in product
            assert "name" in product
            assert "category" in product
            assert "halal_status" in product
            assert "certification_body" in product
            assert "last_verified" in product

    def test_haram_products_present(self):
        from data.products import search_products
        result = search_products("pork")
        assert result["total"] > 0
        assert all(r["halal_status"] == "haram" for r in result["results"])

    def test_doubtful_products_present(self):
        from data.products import get_brand_stats
        stats = get_brand_stats()
        assert stats["verdicts"]["doubtful"] > 0


class TestProductsEndpoint:
    """Tests for the products API endpoints."""

    def test_search_endpoint_basic(self):
        response = client.get("/api/v1/products/search?q=Nutella")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert data["query"] == "Nutella"
        assert len(data["results"]) > 0

    def test_search_endpoint_no_results(self):
        response = client.get("/api/v1/products/search?q=zzznonexistentzzz")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_search_endpoint_pagination(self):
        response = client.get("/api/v1/products/search?q=Coca-Cola&limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 2
        assert len(data["results"]) <= 2

    def test_stats_endpoint(self):
        response = client.get("/api/v1/products/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] >= 1000
        assert data["total_brands"] >= 5
        assert "halal" in data["verdicts"]

    def test_barcode_lookup_found(self):
        response = client.get("/api/v1/products/barcode/3017620422003")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Nutella 200g"
        assert data["halal_status"] == "halal"

    def test_barcode_lookup_not_found(self):
        response = client.get("/api/v1/products/barcode/9999999999999")
        assert response.status_code == 404

