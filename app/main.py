"""Halal Check API - Phase 1 + Phase 3 (Barcode Lookup) + Phase 4 (Rate Limiting + Auth)

A REST API that checks food ingredients for halal/haram status.
Supports direct ingredient checking and barcode-based product lookup.
Includes tier-based rate limiting (free/pro/enterprise) and auth.
"""

import asyncio
import logging
import re

from fastapi import FastAPI, HTTPException, Query, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from data.ingredients import lookup_ingredient, check_ingredients, INGREDIENTS
from data.products import search_products, get_product_by_barcode, get_products_count, get_brand_stats
from app.barcode import assess_barcode, BarcodeAssessment
from app.ratelimit import rate_limiter, RateLimiter, TIERS
from app.auth import (
    auth_store,
    RegisterRequest,
    RegisterResponse,
    SubscribeRequest,
    SubscribeResponse,
    RevokeResponse,
    KeysResponse,
    KeyInfo,
    PolarSubscribeRequest,
    PolarSubscribeResponse,
    PolarPortalResponse,
)
from app.polar import (
    create_checkout_session,
    create_billing_portal_session,
    verify_webhook_signature,
    process_webhook_event,
    apply_webhook_action,
    is_configured as polar_is_configured,
)

app = FastAPI(
    title="Halal Check API",
    description="Check food ingredients for halal/haram/doubtful status. Supports direct ingredient lookup and barcode-based product scanning via Open Food Facts.",
    version="0.5.0",
)

logger = logging.getLogger(__name__)


# --- API Key Extraction Helper ---

def _extract_api_key(request: Request) -> str:
    """Extract API key from header or query parameter."""
    api_key=request.headers.get("X-API-Key") or request.query_params.get("api_key", "anonymous")
    return api_key


def _sync_auth_tier(api_key: str) -> None:
    if api_key == "anonymous":
        return
    user = auth_store.get_user_by_key(api_key)
    if user and user.active:
        rate_limiter.set_tier(api_key, user.subscription.tier)


# --- Rate Limit Dependency ---

class RateLimitContext:
    """Holds rate limit info for the current request."""
    def __init__(self, api_key: str, tier_name: str):
        self.api_key = api_key
        self.tier_name = tier_name


async def require_rate_limit(
    request: Request,
    cost: int = 1,
) -> RateLimitContext:
    """FastAPI dependency that enforces rate limits.

    Usage in endpoint:
        @app.get("/endpoint")
        async def my_endpoint(ctx: RateLimitContext = Depends(lambda r: require_rate_limit(r, cost=1))):
            ...
    """
    api_key = _extract_api_key(request)
    _sync_auth_tier(api_key)
    allowed, headers = rate_limiter.check_rate_limit(api_key, cost=cost)

    # Store headers on request state so middleware can inject them into response
    request.state.rate_limit_headers = headers

    if not allowed:
        request.state.rate_limit_blocked = True
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": "You have exceeded the rate limit for your tier. "
                           "Upgrade your plan or wait before retrying.",
                "retry_after": headers.get("Retry-After"),
                "tier": headers.get("X-RateLimit-Tier"),
                "limits": {
                    "minute": headers.get("X-RateLimit-Limit-Minute"),
                    "daily": headers.get("X-RateLimit-Limit-Day"),
                },
            },
            headers=headers,
        )

    rate_limiter.record_request(api_key, cost=cost)
    tier = rate_limiter.get_tier(api_key)
    return RateLimitContext(api_key=api_key, tier_name=tier.name)


# --- Middleware to inject rate limit headers ---

@app.middleware("http")
async def rate_limit_headers_middleware(request: Request, call_next):
    """Inject X-RateLimit-* headers into every response."""
    response: Response = await call_next(request)

    if hasattr(request.state, "rate_limit_headers"):
        for key, value in request.state.rate_limit_headers.items():
            response.headers[key] = value

    return response


# --- Request/Response Models ---

class CheckRequest(BaseModel):
    ingredients: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of ingredient names or E-numbers to check",
        examples=[["gelatin", "sugar", "E120", "olive oil"]],
    )


class IngredientResult(BaseModel):
    query: str
    name: str
    verdict: str  # halal, haram, doubtful, unknown
    reason: str
    source: Optional[str] = None
    e_number: Optional[str] = None


class CheckResponse(BaseModel):
    total: int
    halal: int
    haram: int
    doubtful: int
    unknown: int
    results: list[IngredientResult]
    overall_verdict: str  # halal, haram, doubtful, or mixed


class HealthResponse(BaseModel):
    status: str
    version: str
    database_entries: int


# --- Barcode Response Models ---

class FlaggedIngredient(BaseModel):
    name: str
    verdict: str
    reason: str
    e_number: Optional[str] = None


class ParsedIngredientResponse(BaseModel):
    name: str
    verdict: str
    reason: str
    e_number: Optional[str] = None


class BarcodeResponse(BaseModel):
    barcode: str
    product_name: Optional[str]
    brand: Optional[str]
    ingredients_text: Optional[str]
    overall_status: str
    confidence: float
    flagged_ingredients: list[FlaggedIngredient]
    ingredient_count: int
    halal_count: int
    haram_count: int
    doubtful_count: int
    unknown_count: int
    has_halal_certification: bool
    certification_labels: list[str]
    all_ingredients: list[ParsedIngredientResponse]
    source: str


# --- Endpoints ---

@app.get("/api/v1/health", response_model=HealthResponse, tags=["system"])
async def health_check(request: Request):
    """Health check endpoint (no rate limiting)."""
    # Still set rate limit headers for informational purposes
    api_key = _extract_api_key(request)
    _, headers = rate_limiter.check_rate_limit(api_key)
    _sync_auth_tier(api_key)
    request.state.rate_limit_headers = headers
    return HealthResponse(
        status="ok",
        version="0.5.0",
        database_entries=len(INGREDIENTS),
    )



@app.get("/api/v1/ingredient/{name}", response_model=IngredientResult, tags=["ingredients"])
async def get_ingredient(name: str, request: Request):
    """Look up a single ingredient by name or E-number.

    Rate limited: costs 1 request per call.
    Pass X-API-Key header to identify your client for rate limiting.
    """
    await require_rate_limit(request, cost=1)
    result = lookup_ingredient(name)
    if not result:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Ingredient not found",
                "query": name,
                "message": "This ingredient is not in our database. Please verify independently.",
            },
        )
    return IngredientResult(
        query=name,
        name=result["name"],
        verdict=result["verdict"],
        reason=result["reason"],
        source=result.get("source"),
        e_number=result.get("e_number"),
    )


@app.post("/api/v1/check", response_model=CheckResponse, tags=["ingredients"])
async def check_ingredients_endpoint(request: Request, body: CheckRequest):
    """Check a list of ingredients for halal status.

    Returns individual verdicts and an overall assessment.
    Any haram ingredient makes the overall verdict haram.
    Any doubtful ingredient (without haram) makes it doubtful.

    Rate limited: costs 1 request per call.
    Pass X-API-Key header to identify your client for rate limiting.
    """
    await require_rate_limit(request, cost=1)
    results = check_ingredients(body.ingredients)

    halal_count = sum(1 for r in results if r["verdict"] == "halal")
    haram_count = sum(1 for r in results if r["verdict"] == "haram")
    doubtful_count = sum(1 for r in results if r["verdict"] == "doubtful")
    unknown_count = sum(1 for r in results if r["verdict"] == "unknown")

    # Determine overall verdict
    if haram_count > 0:
        overall = "haram"
    elif doubtful_count > 0 or unknown_count > 0:
        overall = "doubtful"
    else:
        overall = "halal"

    return CheckResponse(
        total=len(results),
        halal=halal_count,
        haram=haram_count,
        doubtful=doubtful_count,
        unknown=unknown_count,
        results=results,
        overall_verdict=overall,
    )


@app.get("/api/v1/barcode/{barcode}", response_model=BarcodeResponse, tags=["barcode"])
async def get_barcode_assessment(barcode: str, request: Request):
    """
    Look up a product by barcode and assess its halal status.

    Fetches product data from Open Food Facts, extracts ingredients,
    and checks each ingredient against our halal/haram database.
    Results are cached for 24 hours.

    Returns 404 if the barcode is not found in Open Food Facts.

    Rate limited: costs 1 request per call.
    Pass X-API-Key header to identify your client for rate limiting.
    """
    await require_rate_limit(request, cost=1)
    # Validate barcode format
    barcode = barcode.strip()
    if not re.match(r'^\d{8,14}$', barcode):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid barcode format",
                "message": "Barcode must be 8-14 digits.",
                "example": "3017620422003",
            },
        )

    try:
        assessment = await assess_barcode(barcode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "External API error",
                "message": f"Failed to fetch product data: {str(e)}",
            },
        )

    # Check if product was found
    if assessment.product_name is None and assessment.overall_status == "unknown":
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Product not found",
                "barcode": barcode,
                "message": "This barcode was not found in the Open Food Facts database.",
            },
        )

    halal_count = sum(1 for i in assessment.all_ingredients if i.verdict == "halal")
    haram_count = sum(1 for i in assessment.all_ingredients if i.verdict == "haram")
    doubtful_count = sum(1 for i in assessment.all_ingredients if i.verdict == "doubtful")
    unknown_count = sum(1 for i in assessment.all_ingredients if i.verdict == "unknown")

    return BarcodeResponse(
        barcode=assessment.barcode,
        product_name=assessment.product_name,
        brand=assessment.brand,
        ingredients_text=assessment.ingredients_text,
        overall_status=assessment.overall_status,
        confidence=assessment.confidence,
        flagged_ingredients=[
            FlaggedIngredient(**f) for f in assessment.flagged_ingredients
        ],
        ingredient_count=len(assessment.all_ingredients),
        halal_count=halal_count,
        haram_count=haram_count,
        doubtful_count=doubtful_count,
        unknown_count=unknown_count,
        has_halal_certification=assessment.has_halal_certification,
        certification_labels=assessment.certification_labels,
        all_ingredients=[
            ParsedIngredientResponse(
                name=i.name,
                verdict=i.verdict,
                reason=i.reason,
                e_number=i.e_number,
            )
            for i in assessment.all_ingredients
        ],
        source=assessment.source,
    )


# --- Batch Barcode ---

class BatchBarcodeRequest(BaseModel):
    barcodes: list[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of product barcodes to check (8-14 digits each)",
        examples=[["3017620422003", "5000159484695", "3228021170197"]],
    )


class BatchItemResult(BaseModel):
    barcode: str
    status: str  # "success" or "error"
    product_name: Optional[str] = None
    brand: Optional[str] = None
    overall_status: Optional[str] = None
    confidence: Optional[float] = None
    flagged_ingredients: list[FlaggedIngredient] = []
    ingredient_count: int = 0
    halal_count: int = 0
    haram_count: int = 0
    doubtful_count: int = 0
    unknown_count: int = 0
    has_halal_certification: bool = False
    error: Optional[str] = None


class BatchBarcodeResponse(BaseModel):
    total: int
    successful: int
    failed: int
    results: list[BatchItemResult]


def _assessment_to_batch_item(assessment: BarcodeAssessment) -> BatchItemResult:
    """Convert a BarcodeAssessment to a BatchItemResult."""
    return BatchItemResult(
        barcode=assessment.barcode,
        status="success",
        product_name=assessment.product_name,
        brand=assessment.brand,
        overall_status=assessment.overall_status,
        confidence=assessment.confidence,
        flagged_ingredients=[
            FlaggedIngredient(**f) for f in assessment.flagged_ingredients
        ],
        ingredient_count=len(assessment.all_ingredients),
        halal_count=sum(1 for i in assessment.all_ingredients if i.verdict == "halal"),
        haram_count=sum(1 for i in assessment.all_ingredients if i.verdict == "haram"),
        doubtful_count=sum(1 for i in assessment.all_ingredients if i.verdict == "doubtful"),
        unknown_count=sum(1 for i in assessment.all_ingredients if i.verdict == "unknown"),
        has_halal_certification=assessment.has_halal_certification,
    )


async def _assess_single_barcode(barcode: str) -> BatchItemResult:
    """Assess a single barcode, returning a BatchItemResult. Never raises."""
    barcode = barcode.strip()
    if not barcode or not re.match(r'^\d{8,14}$', barcode):
        return BatchItemResult(
            barcode=barcode,
            status="error",
            error="Invalid barcode format. Must be 8-14 digits.",
        )

    try:
        assessment = await assess_barcode(barcode)
    except Exception as e:
        return BatchItemResult(
            barcode=barcode,
            status="error",
            error=f"Failed to process: {str(e)}",
        )

    if assessment.product_name is None and assessment.overall_status == "unknown":
        return BatchItemResult(
            barcode=barcode,
            status="error",
            error="Product not found in Open Food Facts database.",
        )

    return _assessment_to_batch_item(assessment)


@app.post("/api/v1/barcode/batch", response_model=BatchBarcodeResponse, tags=["barcode"])
async def batch_barcode_check(request: Request, body: BatchBarcodeRequest):
    """
    Check multiple barcodes at once (up to 50).

    Processes all barcodes in parallel for maximum performance.
    Returns partial results even if some barcodes fail.
    Each item includes a status field: "success" or "error".

    Rate limited: costs 1 request per barcode checked.
    Batch endpoint is only available for Pro and Enterprise tiers.
    Free tier users will receive 403.

    Pass X-API-Key header to identify your client for rate limiting.
    """
    # Check tier permission first
    api_key = _extract_api_key(request)
    _sync_auth_tier(api_key)
    tier = rate_limiter.get_tier(api_key)

    if not tier.batch_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Batch endpoint requires Pro or Enterprise tier",
                "message": "Upgrade your plan to access batch barcode scanning.",
                "current_tier": tier.name,
                "required_tier": "pro",
                "upgrade_url": "/api/v1/auth/subscribe",
            },
        )

    if len(body.barcodes) > tier.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Batch size exceeds tier limit",
                "message": f"Your {tier.name} tier allows up to {tier.max_batch_size} barcodes per batch.",
                "provided": len(body.barcodes),
                "max_allowed": tier.max_batch_size,
            },
        )

    # Rate limit: 1 request per barcode
    cost = len([bc for bc in body.barcodes if bc.strip() and re.match(r'^\d{8,14}$', bc.strip())])
    await require_rate_limit(request, cost=cost)
    # Validate all barcode formats upfront
    valid_barcodes = []
    for bc in body.barcodes:
        bc_stripped = bc.strip()
        if not bc_stripped:
            continue
        if re.match(r'^\d{8,14}$', bc_stripped):
            valid_barcodes.append(bc_stripped)

    # Process in parallel
    tasks = [_assess_single_barcode(bc) for bc in valid_barcodes]
    results = await asyncio.gather(*tasks)

    successful = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "error")

    return BatchBarcodeResponse(
        total=len(results),
        successful=successful,
        failed=failed,
        results=list(results),
    )


# --- Usage Tracking Endpoint ---

class UsageTierFeatures(BaseModel):
    batch_enabled: bool
    max_batch_size: int
    detailed_results: bool


class UsagePeriodStats(BaseModel):
    used: int
    limit: int
    remaining: int


class UsagePeriod(BaseModel):
    minute: UsagePeriodStats
    day: UsagePeriodStats


class UsageResponse(BaseModel):
    tier: str
    current_period: UsagePeriod
    features: UsageTierFeatures


@app.get("/api/v1/auth/usage", response_model=UsageResponse, tags=["auth"])
async def get_usage(request: Request):
    """
    Get current API usage statistics for your API key.

    Returns daily and per-minute consumption, remaining quota,
    and feature availability based on your tier.

    Pass X-API-Key header to identify your client.
    This endpoint does not count against your rate limit.
    """
    api_key = _extract_api_key(request)
    usage = rate_limiter.get_usage(api_key)
    _sync_auth_tier(api_key)
    return UsageResponse(**usage)


# --- Auth Endpoints (Registration, Keys, Subscribe) ---

@app.post("/api/v1/auth/register", response_model=RegisterResponse, tags=["auth"])
async def register(body: RegisterRequest):
    """
    Register a new account and receive an API key.

    The API key is returned exactly once. Save it securely.
    You'll pass it as X-API-Key header in all API requests.
    New accounts start on the Free tier.
    """
    try:
        raw_key = auth_store.create_user(email=body.email, name=body.name)
    except ValueError as e:
        raise HTTPException(status_code=409, detail={"error": str(e)})

    user = auth_store.get_user_by_key(raw_key)
    return RegisterResponse(
        api_key=raw_key,
        api_key_prefix=user.api_key_prefix,
        email=user.email,
        name=user.name,
        tier=user.subscription.tier,
        message="Store your API key securely. Pass it as X-API-Key header in all requests.",
    )


@app.get("/api/v1/auth/keys", response_model=KeysResponse, tags=["auth"])
async def list_keys(request: Request):
    """
    List information about your registered API key.

    Pass X-API-Key header to identify yourself.
    Returns your current tier, subscription status, and key details.
    """
    api_key = _extract_api_key(request)
    if api_key == "anonymous":
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "message": "Pass X-API-Key header."},
        )

    user = auth_store.get_user_by_key(api_key)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid API key", "message": "The provided API key is not recognized."},
        )

    return KeysResponse(
        keys=[KeyInfo(
            api_key_prefix=user.api_key_prefix,
            email=user.email,
            name=user.name,
            tier=user.subscription.tier,
            subscription_active=user.subscription.is_active,
            days_remaining=user.subscription.days_remaining(),
            created_at=user.created_at,
        )],
        count=1,
    )


@app.post("/api/v1/auth/key/revoke", response_model=RevokeResponse, tags=["auth"])
async def revoke_key(request: Request):
    """
    Revoke your current API key.

    The key will be permanently deactivated. You can register again
    with the same email to get a new key.
    """
    api_key = _extract_api_key(request)
    if api_key == "anonymous":
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "message": "Pass X-API-Key header."},
        )

    revoked = auth_store.revoke_key(api_key)
    if not revoked:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid API key", "message": "The provided API key is not recognized."},
        )

    return RevokeResponse(
        revoked=True,
        message="API key has been revoked. Register again to get a new key.",
    )


@app.post("/api/v1/auth/subscribe", response_model=SubscribeResponse, tags=["auth"])
async def subscribe(body: SubscribeRequest, request: Request):
    """
    Manually upgrade your subscription tier.

    This is a manual subscription endpoint for testing/demo purposes.
    For production payments, use /api/v1/auth/subscribe/polar.

    Tier options:
    - free: Basic access (single barcode, basic results)
    - pro: Batch scanning, detailed breakdown, export
    - enterprise: API webhooks, priority support, custom limits

    Pass X-API-Key header to identify yourself.
    """
    api_key = _extract_api_key(request)
    if api_key == "anonymous":
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "message": "Pass X-API-Key header."},
        )

    if body.tier not in ("free", "pro", "enterprise"):
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid tier", "message": "Must be one of: free, pro, enterprise"},
        )

    try:
        result = auth_store.subscribe(api_key, body.tier, body.duration_days)
    except ValueError as e:
        raise HTTPException(status_code=401, detail={"error": str(e)})

    # Sync tier to rate limiter
    rate_limiter.set_tier(api_key, body.tier)

    return SubscribeResponse(
        **result,
        message=f"Successfully subscribed to {body.tier} tier for {body.duration_days} days.",
    )


@app.post("/api/v1/auth/subscribe/polar", response_model=PolarSubscribeResponse, tags=["auth"])
async def subscribe_polar(body: PolarSubscribeRequest, request: Request):
    """
    Create a Polar Checkout Session for Pro tier subscription.

    Pricing:
    - Pro Monthly: $9/month
    - Pro Yearly: $79/year (save ~27%)

    After successful payment, Polar will send a webhook that automatically
    activates your subscription. You'll need to authenticate with X-API-Key.

    Pass X-API-Key header to identify yourself.
    """
    if not polar_is_configured():
        return PolarSubscribeResponse(
            message="Polar is not configured. Set the required environment variables. Use POST /api/v1/auth/subscribe for manual tier upgrades.",
            checkout_url=None,
            status="not_configured",
        )

    api_key = _extract_api_key(request)
    if api_key == "anonymous":
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "message": "Pass X-API-Key header."},
        )

    user = auth_store.get_user_by_key(api_key)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid API key", "message": "The provided API key is not recognized."},
        )

    try:
        result = create_checkout_session(
            user_email=user.email,
            api_key=api_key,
            tier=body.tier,
            billing_period=body.billing_period,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Polar error", "message": str(e)},
        )

    return PolarSubscribeResponse(
        message=f"Redirect to Polar checkout to complete your {body.billing_period} Pro subscription.",
        checkout_url=result["checkout_url"],
        session_id=result["session_id"],
        status="success",
    )


@app.get("/api/v1/auth/billing/portal", response_model=PolarPortalResponse, tags=["auth"])
async def billing_portal(request: Request):
    """
    Get a link to the Polar Customer Portal for managing your subscription.

    From the portal, users can:
    - View subscription details
    - Cancel their subscription
    - Update payment methods
    - Download invoices

    Pass X-API-Key header to identify yourself.
    """
    if not polar_is_configured():
        return PolarPortalResponse(
            message="Polar is not configured.",
            portal_url=None,
            status="not_configured",
        )

    api_key = _extract_api_key(request)
    if api_key == "anonymous":
        raise HTTPException(
            status_code=401,
            detail={"error": "Authentication required", "message": "Pass X-API-Key header."},
        )

    user = auth_store.get_user_by_key(api_key)
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": "Invalid API key", "message": "The provided API key is not recognized."},
        )

    if not user.subscription.polar_customer_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "No Polar customer found",
                "message": "You don't have an active Polar subscription. Subscribe first via POST /api/v1/auth/subscribe/polar.",
            },
        )

    try:
        result = create_billing_portal_session(user.subscription.polar_customer_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Polar error", "message": str(e)},
        )

    return PolarPortalResponse(
        message="Billing portal session created. Redirect user to portal_url to manage their subscription.",
        portal_url=result["portal_url"],
        status="success",
    )


@app.post("/api/v1/webhooks/polar", tags=["webhooks"])
async def polar_webhook(request: Request):
    """
    Polar webhook endpoint.

    Handles the following events:
    - subscription.created: Activates subscription after checkout
    - subscription.active: Activates subscription on renewal
    - subscription.canceled: Cancels subscription
    - subscription.revoked: Terminates subscription immediately
    - subscription.past_due: Grants 7-day grace period for failed payment
    - subscription.updated: Updates subscription on changes

    This endpoint is called by Polar, not by users.
    """
    payload = await request.body()
    sig_header = request.headers.get("polar-webhook-signature", "")

    if not sig_header:
        raise HTTPException(status_code=400, detail={"error": "Missing polar-webhook-signature header"})

    # Verify webhook signature
    try:
        event = verify_webhook_signature(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})

    # Process the event
    action_result = process_webhook_event(event)

    # Apply the action to auth store
    try:
        apply_webhook_action(auth_store, action_result)
    except Exception as e:
        logger.error("Failed to apply webhook action: %s", e)
        # Return 200 anyway to prevent Polar retries for non-critical errors

    # Sync tier to rate limiter if we have a user
    if action_result.get("api_key_hash") and action_result.get("action") != "ignore":
        user = auth_store.get_user_by_hash(action_result["api_key_hash"])
        if user:
            # The rate limiter uses raw keys, so we store tier update
            # Rate limiter will pick up the new tier on next request via _sync_auth_tier
            pass

    return {"received": True, "event_type": action_result["event_type"], "action": action_result["action"]}


# --- Products Search (Phase 2.5) ---

class ProductSearchResponse(BaseModel):
    total: int
    query: str
    limit: int
    offset: int
    results: list[dict]


class ProductStatsResponse(BaseModel):
    total_products: int
    total_brands: int
    verdicts: dict
    top_brands: list[tuple]


@app.get("/api/v1/products/search", response_model=ProductSearchResponse, tags=["products"])
async def search_products_endpoint(
    request: Request,
    q: str = Query(..., min_length=1, max_length=200, description="Search query (product name, brand, or barcode)"),
    limit: int = Query(50, ge=1, le=100, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """Search the product database by name, brand, or barcode.

    Returns pre-computed halal status for common brand products.
    Rate limited: costs 1 request per call.
    """
    await require_rate_limit(request, cost=1)
    result = search_products(q, limit=limit, offset=offset)
    return ProductSearchResponse(
        total=result["total"],
        query=result["query"],
        limit=result["limit"],
        offset=result["offset"],
        results=result["results"],
    )


@app.get("/api/v1/products/stats", response_model=ProductStatsResponse, tags=["products"])
async def products_stats_endpoint(request: Request):
    """Get statistics about the product database.

    Returns product counts, brand breakdown, and verdict distribution.
    Rate limited: costs 1 request per call.
    """
    await require_rate_limit(request, cost=1)
    stats = get_brand_stats()
    return ProductStatsResponse(
        total_products=stats["total_products"],
        total_brands=stats["total_brands"],
        verdicts=stats["verdicts"],
        top_brands=stats["top_brands"],
    )


@app.get("/api/v1/products/barcode/{barcode}", tags=["products"])
async def get_product_endpoint(request: Request, barcode: str):
    """Look up a product by its exact EAN/UPC barcode.

    Returns the full product record with pre-computed halal status.
    Rate limited: costs 1 request per call.
    """
    await require_rate_limit(request, cost=1)
    product = get_product_by_barcode(barcode)
    if not product:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Product not found",
                "barcode": barcode,
                "message": "This barcode is not in our product database. "
                           "Try the barcode endpoint for real-time Open Food Facts lookup.",
            },
        )
    return product


# --- App Entry Point ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
