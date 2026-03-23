"""
Weekly report generator — generates automated uptime/latency/error reports.

Can be run as a standalone script or integrated with cron/scheduler.
Outputs a structured report suitable for logging, email, or webhook delivery.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from monitoring.health_monitor import HealthMonitor, UptimeStats

logger = logging.getLogger(__name__)


@dataclass
class WeeklyReport:
    """A weekly monitoring report."""
    generated_at: str
    period_hours: float
    total_checks: int
    successful_checks: int
    failed_checks: int
    uptime_percentage: float
    avg_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    error_rate: float
    p95_response_time_ms: Optional[float] = None
    p99_response_time_ms: Optional[float] = None
    last_failure: Optional[str] = None
    consecutive_failures_at_report: int = 0
    alert_count: int = 0
    status: str = "healthy"  # healthy, degraded, critical


def compute_percentile(sorted_values: list[float], percentile: float) -> float:
    """Compute a percentile from a sorted list of values."""
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * percentile / 100)
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


def generate_weekly_report(
    monitor: HealthMonitor,
    hours: float = 168,  # 7 days
    alert_count: int = 0,
) -> WeeklyReport:
    """
    Generate a weekly report from the health monitor's history.
    
    Args:
        monitor: The HealthMonitor instance with collected data
        hours: Report period in hours (default 168 = 7 days)
        alert_count: Number of alerts fired during the period
    
    Returns:
        WeeklyReport dataclass
    """
    stats = monitor.get_stats(window_hours=hours)
    recent = monitor.get_recent_results(limit=10000)

    # Filter to the report window
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    window_results = [r for r in recent if r.timestamp >= cutoff]

    # Compute percentiles from successful response times
    response_times = sorted([r.response_time_ms for r in window_results if r.is_up])
    p95 = compute_percentile(response_times, 95)
    p99 = compute_percentile(response_times, 99)

    # Determine status
    if stats.uptime_percentage >= 99.5 and stats.error_rate < 1.0:
        status = "healthy"
    elif stats.uptime_percentage >= 95.0 and stats.error_rate < 5.0:
        status = "degraded"
    else:
        status = "critical"

    report = WeeklyReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        period_hours=hours,
        total_checks=stats.total_checks,
        successful_checks=stats.successful_checks,
        failed_checks=stats.failed_checks,
        uptime_percentage=stats.uptime_percentage,
        avg_response_time_ms=stats.avg_response_time_ms,
        max_response_time_ms=stats.max_response_time_ms,
        min_response_time_ms=stats.min_response_time_ms,
        error_rate=stats.error_rate,
        p95_response_time_ms=round(p95, 2) if response_times else None,
        p99_response_time_ms=round(p99, 2) if response_times else None,
        last_failure=stats.last_failure.isoformat() if stats.last_failure else None,
        consecutive_failures_at_report=stats.consecutive_failures,
        alert_count=alert_count,
        status=status,
    )

    return report


def format_report_text(report: WeeklyReport) -> str:
    """Format a WeeklyReport as human-readable text."""
    lines = [
        "=" * 60,
        "  HALAL CHECK API — WEEKLY MONITORING REPORT",
        "=" * 60,
        f"  Generated: {report.generated_at}",
        f"  Period:    last {report.period_hours:.0f} hours ({report.period_hours / 24:.1f} days)",
        f"  Status:    {report.status.upper()}",
        "",
        "  --- UPTIME ---",
        f"  Total checks:     {report.total_checks}",
        f"  Successful:       {report.successful_checks}",
        f"  Failed:           {report.failed_checks}",
        f"  Uptime:           {report.uptime_percentage}%",
        f"  Error rate:       {report.error_rate}%",
        "",
        "  --- LATENCY (ms) ---",
        f"  Average:          {report.avg_response_time_ms}",
        f"  Min:              {report.min_response_time_ms}",
        f"  Max:              {report.max_response_time_ms}",
    ]

    if report.p95_response_time_ms is not None:
        lines.append(f"  P95:              {report.p95_response_time_ms}")
    if report.p99_response_time_ms is not None:
        lines.append(f"  P99:              {report.p99_response_time_ms}")

    lines.extend([
        "",
        "  --- ALERTS ---",
        f"  Alerts in period: {report.alert_count}",
    ])

    if report.last_failure:
        lines.append(f"  Last failure:     {report.last_failure}")

    if report.consecutive_failures_at_report > 0:
        lines.append(f"  ⚠  Current consecutive failures: {report.consecutive_failures_at_report}")

    lines.append("=" * 60)

    return "\n".join(lines)


def format_report_json(report: WeeklyReport) -> str:
    """Format a WeeklyReport as JSON."""
    return json.dumps(asdict(report), indent=2)
