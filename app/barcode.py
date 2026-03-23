"""
Barcode lookup module - integrates with Open Food Facts API.

Provides barcode-to-halal-assessment conversion by:
1. Fetching product data from OFF API
2. Extracting and parsing ingredients
3. Running each ingredient through the halal checker
4. Caching results (TTL 24h)
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, cast

import httpx
from cachetools import TTLCache

from app.observability import instrument_cache_get
from data.ingredients import lookup_ingredient

logger = logging.getLogger(__name__)


def _coerce_display_str(value: object) -> str | None:
    """Normalize OFF product fields to optional string for API responses."""
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    if isinstance(value, int | float | bool):
        return str(value)
    if isinstance(value, dict | list):
        return None
    return str(value)


# OFF API base URL
OFF_API_BASE = "https://world.openfoodfacts.org/api/v2"

# Cache: 24h TTL, max 1000 entries (OFF payloads, assessments, and negative cache None)
_cache: TTLCache[str, Any] = TTLCache(maxsize=1000, ttl=86400)


@dataclass
class ParsedIngredient:
    """A single parsed ingredient with its halal assessment."""
    raw: str
    name: str
    verdict: str  # halal, haram, doubtful, unknown
    reason: str
    e_number: str | None = None


@dataclass
class BarcodeAssessment:
    """Full assessment of a product by barcode."""
    barcode: str
    product_name: str | None
    brand: str | None
    ingredients_text: str | None
    flagged_ingredients: list[dict]
    all_ingredients: list[ParsedIngredient]
    overall_status: str  # halal, haram, doubtful, unknown
    confidence: float  # 0.0 - 1.0
    has_halal_certification: bool
    certification_labels: list[str]
    source: str
    cache_hit: bool


def _remove_percentages(text: str) -> str:
    """Remove percentage values from ingredient text (e.g., '13%', '7.4%')."""
    return re.sub(r'\s*\d+(?:\.\d+)?\s*%', '', text)


def _remove_qualifiers(text: str) -> str:
    """Remove common qualifiers like 'organic', 'natural', etc."""
    qualifiers = [
        r'\borganic\b',
        r'\bnatural\b',
        r'\bconcentrated\b',
        r'\bpowdered\b',
        r'\bdried\b',
        r'\bfresh\b',
        r'\bfrozen\b',
        r'\bpasteurized\b',
        r'\bhomogenized\b',
        r'\bunbleached\b',
        r'\benriched\b',
    ]
    for q in qualifiers:
        text = re.sub(q, '', text, flags=re.IGNORECASE)
    return text


def _protect_parenthesized(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace parenthesized content with placeholders to avoid
    splitting on commas inside parentheses.
    Returns (protected_text, {placeholder: original_content}).
    """
    placeholders = {}
    counter = [0]

    def _replace(match):
        key = f"__PAREN_{counter[0]}__"
        placeholders[key] = match.group(1)
        counter[0] += 1
        return key

    protected = re.sub(r'\(([^)]+)\)', _replace, text)
    return protected, placeholders


def _restore_parenthesized(
    text: str, placeholders: dict[str, str]
) -> list[str]:
    """Expand placeholders back into sub-ingredients."""
    results = []
    for key, content in placeholders.items():
        if key in text:
            # Split the content on commas and slashes
            sub_parts = re.split(r'[,/]', content)
            for sp in sub_parts:
                sp_clean = _remove_percentages(sp).strip()
                sp_clean = _remove_qualifiers(sp_clean).strip()
                if sp_clean:
                    results.append(sp_clean)
    return results


def _parse_ingredients_string(ingredients_text: str) -> list[str]:
    """
    Parse a comma-separated ingredient string into individual ingredients.
    Handles:
    - Parenthesized sub-ingredients: "emulsifier (soy lecithin)" -> ["emulsifier", "soy lecithin"]
    - Nested commas: "emulsifier (E471, E472)" -> ["emulsifier", "E471", "E472"]
    - Percentage values: "sugar 38%" -> "sugar"
    - Period-separated (some formats): "water. sugar." -> ["water", "sugar"]
    """
    if not ingredients_text or not ingredients_text.strip():
        return []

    text = ingredients_text.strip()

    # Normalize separators: replace periods followed by space with commas
    text = re.sub(r'\.\s+', ', ', text)
    text = re.sub(r'\.\s*$', '', text)

    # Protect parenthesized content from splitting
    protected, placeholders = _protect_parenthesized(text)

    # Split on commas, semicolons, and "and"
    raw_parts = re.split(r'[;,]|\s+and\s+', protected)

    ingredients = []
    for part in raw_parts:
        part = part.strip()
        if not part:
            continue

        # Remove trailing periods
        part = part.rstrip('.')

        # Extract sub-ingredients from placeholders found in this part
        sub_ingredients = _restore_parenthesized(part, placeholders)

        # Remove placeholders from main part
        main_part = re.sub(r'__PAREN_\d+__', '', part).strip()

        # Clean the main ingredient
        main_clean = _remove_percentages(main_part)
        main_clean = _remove_qualifiers(main_clean).strip()
        if main_clean:
            ingredients.append(main_clean)

        # Add sub-ingredients
        ingredients.extend(sub_ingredients)

    return ingredients


def _detect_halal_certification(product: dict) -> tuple[bool, list[str]]:
    """
    Detect halal certification labels from product data.
    """
    labels = []
    has_cert = False

    # Check labels_tags (handle None / malformed OFF payloads)
    raw_label_tags = product.get("labels_tags") or []
    if isinstance(raw_label_tags, str):
        raw_label_tags = [raw_label_tags]
    elif not isinstance(raw_label_tags, list):
        raw_label_tags = []
    for tag in raw_label_tags:
        if "halal" in tag.lower():
            has_cert = True
            labels.append(tag.replace("en:", "").replace("fr:", "").replace("-", " ").title())

    # Check labels text
    labels_text = product.get("labels", "") or ""
    if "halal" in labels_text.lower():
        has_cert = True
        if labels_text.strip() and labels_text.strip() not in labels:
            labels.append(labels_text.strip())

    # Check categories_tags for halal-related (handle None / malformed)
    raw_cats = product.get("categories_tags") or []
    if isinstance(raw_cats, str):
        raw_cats = [raw_cats]
    elif not isinstance(raw_cats, list):
        raw_cats = []
    for tag in raw_cats:
        if "halal" in tag.lower():
            has_cert = True
            if tag not in labels:
                labels.append(tag.replace("en:", "").title())

    return has_cert, labels


def _compute_confidence(
    all_ingredients: list[ParsedIngredient],
    has_certification: bool,
) -> float:
    """
    Compute a confidence score for the assessment.
    Higher when:
    - More ingredients are known (not unknown)
    - Product has halal certification
    - All known ingredients match the overall status
    """
    if not all_ingredients:
        return 0.0

    known = [i for i in all_ingredients if i.verdict != "unknown"]
    unknown = [i for i in all_ingredients if i.verdict == "unknown"]

    # Base confidence from known ratio
    known_ratio = len(known) / len(all_ingredients)

    # Certification bonus
    cert_bonus = 0.15 if has_certification else 0.0

    # Consistency bonus: if all known ingredients agree with overall
    statuses = set(i.verdict for i in known if i.verdict != "unknown")
    consistency_bonus = 0.1 if len(statuses) <= 1 else 0.0

    # Penalty for many unknowns
    unknown_penalty = 0.0
    if len(all_ingredients) > 0:
        unknown_ratio = len(unknown) / len(all_ingredients)
        if unknown_ratio > 0.5:
            unknown_penalty = 0.2
        elif unknown_ratio > 0.3:
            unknown_penalty = 0.1

    # Cap at 1.0. The test expects certification to increase the score
    # vs no-certification, so apply cert bonus before capping.
    base = known_ratio + consistency_bonus - unknown_penalty
    raw = base + cert_bonus
    return round(min(1.0, max(0.0, raw)), 2)


async def fetch_product_from_off(barcode: str) -> dict | None:
    """
    Fetch product data from Open Food Facts API.
    Returns the product dict if found, None otherwise.
    """
    # Check cache first
    cache_key = f"off:{barcode}"
    cached = _cache.get(cache_key)
    if cached is not None:
        logger.info("Cache hit for barcode %s", barcode)
        instrument_cache_get("off_product", hit=True)
        return cast(dict[str, Any] | None, cached)
    instrument_cache_get("off_product", hit=False)

    url = f"{OFF_API_BASE}/product/{barcode}.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = cast(dict[str, Any], resp.json())

        if data.get("status") == 1 and data.get("product"):
            product = cast(dict[str, Any], data["product"])
            _cache[cache_key] = product
            return product
        else:
            # Cache "not found" for 1 hour to avoid repeat lookups
            _cache[cache_key] = None
            return None

    except (httpx.TimeoutException, TimeoutError):
        logger.warning("Timeout fetching barcode %s from OFF", barcode)
        raise
    except httpx.HTTPError as e:
        logger.error("HTTP error fetching barcode %s: %s", barcode, e)
        raise


async def assess_barcode(barcode: str) -> BarcodeAssessment:
    """
    Main function: take a barcode and return a full halal assessment.
    """
    # Validate barcode format
    barcode = barcode.strip()
    if not re.match(r'^\d{8,14}$', barcode):
        raise ValueError(f"Invalid barcode format: {barcode}. Expected 8-14 digits.")

    # Check cache for assessment
    assess_cache_key = f"assess:{barcode}"
    cached_assessment = _cache.get(assess_cache_key)
    if cached_assessment is not None:
        instrument_cache_get("barcode_assessment", hit=True)
        return cast(BarcodeAssessment, cached_assessment)
    instrument_cache_get("barcode_assessment", hit=False)

    # Fetch from OFF
    product = await fetch_product_from_off(barcode)

    if product is None:
        assessment = BarcodeAssessment(
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
        _cache[assess_cache_key] = assessment
        return assessment

    # Extract product info (OFF may return non-strings; coerce for stable API output)
    product_name = _coerce_display_str(
        product.get("product_name") or product.get("product_name_en"),
    )
    brand = _coerce_display_str(product.get("brands"))

    # Get ingredients text - prefer English, fall back to any language
    ingredients_text = (
        product.get("ingredients_text_en")
        or product.get("ingredients_text")
        or ""
    )

    # Check for halal certification
    has_cert, cert_labels = _detect_halal_certification(product)

    # Parse ingredients
    raw_ingredients = _parse_ingredients_string(ingredients_text)
    parsed = []
    flagged = []

    for raw_name in raw_ingredients:
        # Look up ingredient in our database
        match = lookup_ingredient(raw_name)

        if match:
            verdict = match["verdict"]
            reason = match["reason"]
            e_number = match.get("e_number")
        else:
            verdict = "unknown"
            reason = "Ingredient not found in our database. Please verify independently."
            e_number = None

        parsed_ingredient = ParsedIngredient(
            raw=raw_name,
            name=raw_name,
            verdict=verdict,
            reason=reason,
            e_number=e_number,
        )
        parsed.append(parsed_ingredient)

        # Flag haram and doubtful ingredients
        if verdict in ("haram", "doubtful"):
            flagged.append({
                "name": raw_name,
                "verdict": verdict,
                "reason": reason,
                "e_number": e_number,
            })

    # Determine overall status
    haram_count = sum(1 for i in parsed if i.verdict == "haram")
    doubtful_count = sum(1 for i in parsed if i.verdict == "doubtful")
    unknown_count = sum(1 for i in parsed if i.verdict == "unknown")

    if has_cert and haram_count == 0:
        overall = "halal"
    elif haram_count > 0:
        overall = "haram"
    elif doubtful_count > 0 or unknown_count > 0 and len(parsed) > 0:
        overall = "doubtful"
    elif len(parsed) == 0:
        overall = "unknown"
    else:
        overall = "halal"

    # Compute confidence
    confidence = _compute_confidence(parsed, has_cert)

    assessment = BarcodeAssessment(
        barcode=barcode,
        product_name=product_name,
        brand=brand,
        ingredients_text=ingredients_text if ingredients_text else None,
        flagged_ingredients=flagged,
        all_ingredients=parsed,
        overall_status=overall,
        confidence=confidence,
        has_halal_certification=has_cert,
        certification_labels=cert_labels,
        source="Open Food Facts",
        cache_hit=False,
    )

    _cache[assess_cache_key] = assessment
    return assessment
