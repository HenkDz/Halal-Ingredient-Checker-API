"""
Health monitor — pings the API health endpoint periodically and tracks uptime.

Provides:
- Periodic health checks (configurable interval, default 60s)
- Uptime percentage calculation (rolling window)
- Response time tracking
- Alerting when API is down or degraded
"""

import time
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    timestamp: datetime
    status_code: int
    response_time_ms: float
    is_up: bool
    error: Optional[str] = None
    details: Optional[dict] = None


@dataclass
class UptimeStats:
    """Aggregated uptime statistics."""
    total_checks: int
    successful_checks: int
    failed_checks: int
    uptime_percentage: float
    avg_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    error_rate: float
    period_hours: float
    last_check: Optional[datetime]
    last_failure: Optional[datetime]
    consecutive_failures: int


class HealthMonitor:
    """
    Monitors API health by pinging /api/v1/health periodically.
    
    Usage:
        monitor = HealthMonitor(base_url="http://localhost:8000")
        monitor.start()  # Starts background thread
        
        # Check status
        stats = monitor.get_stats()
        
        # Set alert callback
        monitor.set_alert_callback(my_alert_fn)
        
        monitor.stop()
    """

    DEFAULT_INTERVAL_SECONDS = 60
    ALERT_CONSECUTIVE_FAILURES = 3
    ALERT_ERROR_RATE_THRESHOLD = 0.05  # 5%
    ALERT_LATENCY_THRESHOLD_MS = 2000  # 2 seconds
    HISTORY_WINDOW_HOURS = 168  # 7 days for rolling stats

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        health_path: str = "/api/v1/health",
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
        history_window_hours: float = HISTORY_WINDOW_HOURS,
        timeout_seconds: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.health_path = health_path
        self.interval_seconds = interval_seconds
        self.history_window_hours = history_window_hours
        self.timeout_seconds = timeout_seconds

        self._history: list[HealthCheckResult] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Alert callbacks: called with (alert_type: str, details: dict)
        self._alert_callbacks: list[Callable] = []

        # Current alert state (to avoid spamming)
        self._alert_suppression: dict[str, datetime] = {}

        # Alert suppression duration (don't re-alert for same issue within this window)
        # CRITICAL api_down alerts re-fire quickly (5 min); others suppress longer
        self._alert_suppression_minutes = 5

    def set_alert_callback(self, callback: Callable[[str, dict], None]) -> None:
        """Register an alert callback. Called with (alert_type, details)."""
        self._alert_callbacks.append(callback)

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            logger.warning("Health monitor is already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="health-monitor")
        self._thread.start()
        logger.info(
            "Health monitor started: pinging %s%s every %ds",
            self.base_url, self.health_path, self.interval_seconds,
        )

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval_seconds + 5)
            self._thread = None
        logger.info("Health monitor stopped")

    def check_health(self) -> HealthCheckResult:
        """Perform a single health check. Can be called manually."""
        url = f"{self.base_url}{self.health_path}"
        start = time.monotonic()

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url)

            elapsed_ms = (time.monotonic() - start) * 1000
            is_up = response.status_code == 200

            result = HealthCheckResult(
                timestamp=datetime.now(timezone.utc),
                status_code=response.status_code,
                response_time_ms=round(elapsed_ms, 2),
                is_up=is_up,
                error=None if is_up else f"HTTP {response.status_code}",
                details=response.json() if is_up else None,
            )
        except httpx.ConnectError as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                timestamp=datetime.now(timezone.utc),
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                is_up=False,
                error=f"Connection refused: {e}",
            )
        except httpx.TimeoutException as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                timestamp=datetime.now(timezone.utc),
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                is_up=False,
                error=f"Timeout after {self.timeout_seconds}s: {e}",
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            result = HealthCheckResult(
                timestamp=datetime.now(timezone.utc),
                status_code=0,
                response_time_ms=round(elapsed_ms, 2),
                is_up=False,
                error=f"Unexpected error: {type(e).__name__}: {e}",
            )

        self._record_result(result)
        self._evaluate_alerts(result)
        return result

    def get_stats(self, window_hours: Optional[float] = None) -> UptimeStats:
        """Get aggregated uptime statistics."""
        hours = window_hours or self.history_window_hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with self._lock:
            recent = [r for r in self._history if r.timestamp >= cutoff]

        if not recent:
            return UptimeStats(
                total_checks=0,
                successful_checks=0,
                failed_checks=0,
                uptime_percentage=0.0,
                avg_response_time_ms=0.0,
                max_response_time_ms=0.0,
                min_response_time_ms=0.0,
                error_rate=0.0,
                period_hours=hours,
                last_check=None,
                last_failure=None,
                consecutive_failures=0,
            )

        successful = [r for r in recent if r.is_up]
        failed = [r for r in recent if not r.is_up]
        response_times = [r.response_time_ms for r in successful]

        # Consecutive failures from the end
        consecutive_failures = 0
        for r in reversed(recent):
            if not r.is_up:
                consecutive_failures += 1
            else:
                break

        last_failure = None
        for r in reversed(recent):
            if not r.is_up:
                last_failure = r.timestamp
                break

        return UptimeStats(
            total_checks=len(recent),
            successful_checks=len(successful),
            failed_checks=len(failed),
            uptime_percentage=round(len(successful) / len(recent) * 100, 2),
            avg_response_time_ms=round(sum(response_times) / len(response_times), 2) if response_times else 0.0,
            max_response_time_ms=round(max(response_times), 2) if response_times else 0.0,
            min_response_time_ms=round(min(response_times), 2) if response_times else 0.0,
            error_rate=round(len(failed) / len(recent) * 100, 2),
            period_hours=hours,
            last_check=recent[-1].timestamp if recent else None,
            last_failure=last_failure,
            consecutive_failures=consecutive_failures,
        )

    def get_recent_results(self, limit: int = 100) -> list[HealthCheckResult]:
        """Get the most recent health check results."""
        with self._lock:
            return list(self._history[-limit:])

    def _record_result(self, result: HealthCheckResult) -> None:
        """Record a health check result and prune old entries."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.history_window_hours)
        with self._lock:
            self._history.append(result)
            # Prune old entries and sort by timestamp so iteration is chronological
            self._history = sorted(
                [r for r in self._history if r.timestamp >= cutoff],
                key=lambda r: r.timestamp,
            )

    def _evaluate_alerts(self, result: HealthCheckResult) -> None:
        """Evaluate alerting rules and fire callbacks."""
        now = datetime.now(timezone.utc)

        # Rule 1: API is down (consecutive failures)
        if not result.is_up:
            stats = self.get_stats()
            if stats.consecutive_failures >= self.ALERT_CONSECUTIVE_FAILURES:
                self._fire_alert(
                    "api_down",
                    {
                        "consecutive_failures": stats.consecutive_failures,
                        "last_error": result.error,
                        "timestamp": now.isoformat(),
                    },
                    now,
                )

        # Rule 2: Error rate > 5%
        stats = self.get_stats()
        if stats.error_rate > self.ALERT_ERROR_RATE_THRESHOLD and stats.total_checks >= 10:
            self._fire_alert(
                "high_error_rate",
                {
                    "error_rate_percent": stats.error_rate,
                    "total_checks": stats.total_checks,
                    "failed_checks": stats.failed_checks,
                    "window_hours": stats.period_hours,
                    "timestamp": now.isoformat(),
                },
                now,
            )

        # Rule 3: Latency > 2s
        if result.is_up and result.response_time_ms > self.ALERT_LATENCY_THRESHOLD_MS:
            self._fire_alert(
                "high_latency",
                {
                    "response_time_ms": result.response_time_ms,
                    "threshold_ms": self.ALERT_LATENCY_THRESHOLD_MS,
                    "timestamp": now.isoformat(),
                },
                now,
            )

    def _get_suppression_minutes(self, alert_type: str) -> int:
        """Get suppression duration based on alert severity."""
        suppression_map = {
            "api_down": 5,           # Critical: re-alert every 5 minutes
            "high_error_rate": 30,   # High: re-alert every 30 minutes
            "high_latency": 15,      # Warning: re-alert every 15 minutes
        }
        return suppression_map.get(alert_type, self._alert_suppression_minutes)

    def _fire_alert(self, alert_type: str, details: dict, now: datetime) -> None:
        """Fire alert callbacks with suppression."""
        # Check suppression
        suppress_until = self._alert_suppression.get(alert_type)
        if suppress_until and now < suppress_until:
            return

        # Update suppression (per-alert-type duration)
        suppression_minutes = self._get_suppression_minutes(alert_type)
        self._alert_suppression[alert_type] = now + timedelta(minutes=suppression_minutes)

        logger.warning("ALERT [%s]: %s", alert_type, details)

        for callback in self._alert_callbacks:
            try:
                callback(alert_type, details)
            except Exception as e:
                logger.error("Alert callback error for %s: %s", alert_type, e)

    def _run_loop(self) -> None:
        """Background loop that runs health checks."""
        while self._running:
            try:
                self.check_health()
            except Exception as e:
                logger.error("Health check loop error: %s", e)

            # Sleep in small increments so we can stop quickly
            for _ in range(self.interval_seconds):
                if not self._running:
                    break
                time.sleep(1)
