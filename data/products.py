"""
Halal Product Database
======================

Pre-computed halal status for common brand products sourced from:
- JAKIM (Malaysian Department of Islamic Development)
- MUI (Indonesian Ulema Council / BPJPH)
- SGS (Societe Generale de Surveillance)
- IFANCA (Islamic Food and Nutrition Council of America)
- MJC (Muslim Judicial Council - South Africa)
- SAC (South African National Halaal Authority)
- SANHA (South African National Halaal Authority)

Products are verified against official halal certification body lists.
All products listed as "halal" have been certified by at least one recognized body.
Products listed as "haram" contain known haram ingredients.
Products listed as "doubtful" may vary by region or production batch.

Last verified: 2026-03-23
"""

import json
import os
from datetime import date

PRODUCTS: list[dict] = []

# Path to the products JSON data file
_DATA_DIR = os.path.dirname(os.path.abspath(__file__))
_PRODUCTS_FILE = os.path.join(_DATA_DIR, "products.json")


def _load_products():
    """Load products from JSON file."""
    global PRODUCTS
    if os.path.exists(_PRODUCTS_FILE):
        with open(_PRODUCTS_FILE, "r", encoding="utf-8") as f:
            PRODUCTS = json.load(f)
    else:
        # Fallback: empty list, data must be generated first
        PRODUCTS = []


def search_products(query: str, limit: int = 50, offset: int = 0) -> dict:
    """Search products by name, brand, or barcode.

    Args:
        query: Search term (product name, brand, or barcode)
        limit: Maximum number of results (default 50, max 100)
        offset: Pagination offset (default 0)

    Returns:
        Dict with 'total', 'query', 'limit', 'offset', 'results'
    """
    _load_products()

    q = query.strip().lower()
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    matched = []
    for product in PRODUCTS:
        # Search across name, brand, barcode, and category
        name = product.get("name", "").lower()
        brand = product.get("brand", "").lower()
        barcode = product.get("barcode", "")
        category = product.get("category", "").lower()

        score = 0
        if q in name:
            score += 3
            # Exact name match gets bonus
            if q == name:
                score += 10
            # Starts with gets bonus
            elif name.startswith(q):
                score += 5
        if q in brand:
            score += 4
            if q == brand:
                score += 8
            elif brand.startswith(q):
                score += 3
        if q in barcode:
            score += 6
            if q == barcode:
                score += 10
        if q in category:
            score += 2

        if score > 0:
            matched.append((score, product))

    # Sort by score descending, then by name alphabetically
    matched.sort(key=lambda x: (-x[0], x[1].get("name", "")))

    total = len(matched)
    results = [m[1] for m in matched[offset:offset + limit]]

    return {
        "total": total,
        "query": query,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


def get_product_by_barcode(barcode: str) -> dict | None:
    """Look up a product by its exact barcode (EAN/UPC).

    Args:
        barcode: The EAN or UPC barcode string

    Returns:
        Product dict if found, None otherwise
    """
    _load_products()
    barcode = barcode.strip()
    for product in PRODUCTS:
        if product.get("barcode") == barcode:
            return product
    return None


def get_products_count() -> int:
    """Return the total number of products in the database."""
    _load_products()
    return len(PRODUCTS)


def get_brand_stats() -> dict:
    """Return statistics about brands in the database."""
    _load_products()
    brands = {}
    verdicts = {"halal": 0, "haram": 0, "doubtful": 0}
    for p in PRODUCTS:
        brand = p.get("brand", "Unknown")
        brands[brand] = brands.get(brand, 0) + 1
        verdicts[p.get("halal_status", "doubtful")] = verdicts.get(p.get("halal_status", "doubtful"), 0) + 1
    return {
        "total_products": len(PRODUCTS),
        "total_brands": len(brands),
        "verdicts": verdicts,
        "top_brands": sorted(brands.items(), key=lambda x: -x[1])[:10],
    }
