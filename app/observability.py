"""
Observability module for Halal Check API.

Provides:
- Structured JSON logging via structlog
- Sentry integration (optional, configured via SENTRY_DSN)
- Prometheus metrics (request count, latency, error rate, cache hits)
- Request logging middleware
- Global exception handlers (no stack traces in production)
"""

import os
import time
import logging
import uuid
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from fastapi import FastAPI

logger = structlog.get_logger()

# --- Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

# --- Prometheus Metrics ---
PROMETHEUS_AVAILABLE = False
REQUEST_COUNT = None
REQUEST_LATENCY = None
ERROR_COUNT = None
ACTIVE_REQUESTS = None
CACHE_HIT_COUNT = None
CACHE_MISS_COUNT = None

try:
    from prometheus_client import (
        Counter, Histogram, Gauge,
        generate_latest, CONTENT_TYPE_LATEST, REGISTRY,
    )

    REQUEST_COUNT = Counter(
        "halal_api_requests_total",
        "Total API requests",
        ["method", "endpoint", "status_code"],
    )
    REQUEST_LATENCY = Histogram(
        "halal_api_request_duration_seconds",
        "API request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )
    ERROR_COUNT = Counter(
        "halal_api_errors_total",
        "Total API errors",
        ["method", "endpoint", "error_type"],
    )
    ACTIVE_REQUESTS = Gauge(
        "halal_api_active_requests",
        "Currently active requests",
    )
    CACHE_HIT_COUNT = Counter(
        "halal_api_cache_hits_total",
        "Cache hit count",
        ["cache_type"],
    )
    CACHE_MISS_COUNT = Counter(
        "halal_api_cache_misses_total",
        "Cache miss count",
        ["cache_type"],
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed, metrics disabled")


# --- Structured Logging Setup ---

def _mask_api_key(api_key: str) -> str:
    """Mask API key for safe logging. Shows first 4 and last 4 chars only."""
    if not api_key or api_key == "anonymous":
        return "anonymous"
    if len(api_key) <= 8:
        return "***"
    return f"{api_key[:4]}...{api_key[-4:]}"


def configure_logging() -> None:
    """Configure structlog for structured JSON logging.

    In DEBUG mode, uses human-readable console output.
    In production, emits one JSON object per line.
    """
    log_level = getattr(logging, LOG_LEVEL, logging.INFO)

    if DEBUG:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging so third-party libs (uvicorn, httpx) also output JSON
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        force=True,
    )


# --- Sentry Integration ---

def configure_sentry(app: FastAPI) -> None:
    """Initialize Sentry SDK if SENTRY_DSN is configured."""
    if not SENTRY_DSN:
        logger.info("sentry_not_configured")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=ENVIRONMENT,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            send_default_pii=False,
            before_send=_sentry_before_send,
        )
        logger.info("sentry_initialized", environment=ENVIRONMENT)
    except ImportError:
        logger.warning("sentry_sdk_not_installed")
    except Exception as e:
        logger.error("sentry_init_failed", error=str(e))


def _sentry_before_send(event, hint):
    """Strip sensitive data before sending to Sentry."""
    request = event.get("request", {})
    headers = request.get("headers", {})

    # Mask API key header
    if "x-api-key" in headers:
        headers["x-api-key"] = "[MASKED]"

    # Remove cookies
    if "cookie" in headers:
        headers["cookie"] = "[MASKED]"

    return event


# --- Request Logging Middleware ---

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every API request in structured JSON format.

    Captures: method, path, status, latency, masked API key.
    Skips /metrics and /api/v1/health paths to reduce noise.
    """

    SKIP_PATHS = {"/metrics", "/api/v1/health"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.monotonic()

        # Bind request context for all log entries in this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        if PROMETHEUS_AVAILABLE:
            ACTIVE_REQUESTS.inc()

        try:
            response = await call_next(request)
            latency = time.monotonic() - start_time

            # Extract and mask API key
            api_key = (
                request.headers.get("X-API-Key")
                or request.query_params.get("api_key", "anonymous")
            )
            masked_key = _mask_api_key(api_key)

            # Skip noisy paths
            if request.url.path not in self.SKIP_PATHS:
                if response.status_code < 400:
                    logger.info(
                        "api_request",
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        latency_ms=round(latency * 1000, 2),
                        api_key=masked_key,
                        client_ip=request.client.host if request.client else "unknown",
                    )
                else:
                    logger.warning(
                        "api_request",
                        method=request.method,
                        path=request.url.path,
                        status_code=response.status_code,
                        latency_ms=round(latency * 1000, 2),
                        api_key=masked_key,
                        client_ip=request.client.host if request.client else "unknown",
                    )

            # Prometheus metrics
            if PROMETHEUS_AVAILABLE:
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code=str(response.status_code),
                ).inc()
                REQUEST_LATENCY.labels(
                    method=request.method,
                    endpoint=request.url.path,
                ).observe(latency)

                if response.status_code >= 400:
                    ERROR_COUNT.labels(
                        method=request.method,
                        endpoint=request.url.path,
                        error_type="client" if response.status_code < 500 else "server",
                    ).inc()

            # Attach request ID to response
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as exc:
            latency = time.monotonic() - start_time

            logger.error(
                "api_request_unhandled_error",
                method=request.method,
                path=request.url.path,
                latency_ms=round(latency * 1000, 2),
                error_type=type(exc).__name__,
                error_message=str(exc) if DEBUG else "internal_server_error",
            )

            if PROMETHEUS_AVAILABLE:
                ERROR_COUNT.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    error_type=type(exc).__name__,
                ).inc()
                REQUEST_COUNT.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status_code="500",
                ).inc()
                REQUEST_LATENCY.labels(
                    method=request.method,
                    endpoint=request.url.path,
                ).observe(latency)

            raise
        finally:
            if PROMETHEUS_AVAILABLE:
                ACTIVE_REQUESTS.dec()
            structlog.contextvars.unbind_contextvars("request_id", "method", "path")


# --- Global Exception Handlers ---

def add_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers.

    In production (DEBUG=false), never exposes stack traces or
    internal error details to clients.
    """

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        if DEBUG:
            return JSONResponse(
                status_code=500,
                content={
                    "error": type(exc).__name__,
                    "message": str(exc),
                    "request_id": request_id,
                },
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "request_id": request_id,
                },
            )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4())[:8])

        logger.warning(
            "value_error",
            request_id=request_id,
            path=request.url.path,
            message=str(exc),
        )

        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad request",
                "message": str(exc) if DEBUG else "Invalid request parameters.",
                "request_id": request_id,
            },
        )


# --- Dependency Health Checks ---

async def check_external_api() -> dict:
    """Check Open Food Facts API connectivity."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://world.openfoodfacts.org/api/v2/test.json"
            )
            return {
                "status": "up" if resp.status_code < 500 else "degraded",
                "latency_ms": round(resp.elapsed.total_seconds() * 1000, 2),
                "status_code": resp.status_code,
            }
    except httpx.TimeoutException:
        return {"status": "timeout", "error": "OFF API timed out"}
    except Exception as e:
        return {"status": "down", "error": str(e) if DEBUG else "Connection failed"}


def check_cache() -> dict:
    """Check barcode cache health."""
    try:
        from app.barcode import _cache

        return {
            "status": "ok",
            "entries": len(_cache),
            "maxsize": _cache.maxsize,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# --- Metrics Endpoint Helper ---

def get_metrics() -> tuple[str, str]:
    """Return Prometheus metrics in text exposition format.

    Returns:
        Tuple of (content_type, body).
    """
    if not PROMETHEUS_AVAILABLE:
        return "text/plain", "Prometheus metrics not available. Install prometheus_client."
    return CONTENT_TYPE_LATEST, generate_latest()


# --- Cache Instrumentation ---

def instrument_cache_get(cache_type: str, hit: bool) -> None:
    """Record a cache hit or miss for Prometheus metrics."""
    if PROMETHEUS_AVAILABLE:
        if hit:
            CACHE_HIT_COUNT.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISS_COUNT.labels(cache_type=cache_type).inc()


# --- One-Call Setup ---

def setup_observability(app: FastAPI) -> None:
    """Configure all observability features in one call.

    Call this once after creating the FastAPI app instance:
        app = FastAPI(...)
        setup_observability(app)
    """
    configure_logging()
    configure_sentry(app)
    add_exception_handlers(app)
    logger.info(
        "observability_configured",
        log_level=LOG_LEVEL,
        environment=ENVIRONMENT,
        debug=DEBUG,
        prometheus=PROMETHEUS_AVAILABLE,
        sentry=bool(SENTRY_DSN),
    )
