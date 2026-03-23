#!/usr/bin/env python3
"""
Standalone monitoring runner for Halal Check API.

Can be run:
  1. As a long-running daemon (default):
     python -m monitoring.run
  
  2. As a single health check:
     python -m monitoring.run --once
  
  3. Generate a weekly report:
     python -m monitoring.run --report

Environment variables:
  API_BASE_URL       — API base URL (default: http://localhost:8000)
  WEBHOOK_URL        — Optional webhook URL for alerts (Slack, Discord)
  SMTP_HOST          — Optional SMTP server for email alerts
  SMTP_PORT          — SMTP port (default: 587)
  SMTP_USER          — SMTP username
  SMTP_PASSWORD      — SMTP password
  SMTP_FROM          — From address (default: SMTP_USER)
  SMTP_TO            — Comma-separated recipient addresses
  CHECK_INTERVAL     — Health check interval in seconds (default: 60)
  REPORT_OUTPUT_DIR  — Directory to save weekly reports (auto-generated Mondays at 00:00 UTC)
"""

import argparse
import json
import logging
import os
import sys
import signal

from monitoring.health_monitor import HealthMonitor
from monitoring.alerting import AlertManager, ConsoleAlerter, WebhookAlerter, EmailAlerter
from monitoring.weekly_report import generate_weekly_report, format_report_text, format_report_json


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_monitor_from_env() -> HealthMonitor:
    """Create a HealthMonitor from environment variables."""
    base_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
    interval = int(os.environ.get("CHECK_INTERVAL", "60"))

    return HealthMonitor(
        base_url=base_url,
        interval_seconds=interval,
    )


def create_alert_manager_from_env() -> AlertManager:
    """Create an AlertManager with configured alerters from environment."""
    manager = AlertManager()

    # Always add console alerter
    manager.add_alerter(ConsoleAlerter())

    # Optional webhook alerter
    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url:
        manager.add_alerter(WebhookAlerter(webhook_url=webhook_url))
        print(f"[monitor] Webhook alerter configured: {webhook_url}")

    # Optional email alerter
    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host:
        alerter = EmailAlerter(
            smtp_host=smtp_host,
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            smtp_user=os.environ.get("SMTP_USER", ""),
            smtp_password=os.environ.get("SMTP_PASSWORD", ""),
            from_addr=os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
            to_addrs=os.environ.get("SMTP_TO", "").split(",") if os.environ.get("SMTP_TO") else [],
        )
        manager.add_alerter(alerter)
        print(f"[monitor] Email alerter configured: {smtp_host}")

    return manager


def run_single_check(monitor: HealthMonitor, alert_manager: AlertManager) -> None:
    """Perform a single health check and evaluate alerts."""
    print("[monitor] Performing single health check...")
    result = monitor.check_health()

    status = "UP" if result.is_up else "DOWN"
    print(f"[monitor] Status: {status} | HTTP {result.status_code} | {result.response_time_ms:.1f}ms")
    if result.error:
        print(f"[monitor] Error: {result.error}")

    # Evaluate alerts
    stats = monitor.get_stats()
    metrics = {
        "consecutive_failures": stats.consecutive_failures,
        "error_rate": stats.error_rate,
        "latency_ms": result.response_time_ms,
    }
    fired = alert_manager.evaluate(metrics)
    if fired:
        print(f"[monitor] Fired {len(fired)} alert(s)")


def run_daemon(monitor: HealthMonitor, alert_manager: AlertManager) -> None:
    """Run the monitor as a long-running daemon with automatic weekly reports."""
    import time
    import json as json_mod
    from datetime import datetime, timedelta, timezone

    # Set up signal handlers for graceful shutdown
    def shutdown(signum, frame):
        print("\n[monitor] Shutting down...")
        monitor.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Connect alert manager to monitor
    def on_alert(alert_type: str, details: dict):
        alert_manager.evaluate({
            "consecutive_failures": monitor.get_stats().consecutive_failures,
            "error_rate": monitor.get_stats().error_rate,
            "latency_ms": details.get("response_time_ms", 0),
        })

    monitor.set_alert_callback(on_alert)

    # Weekly report scheduling
    report_output_dir = os.environ.get("REPORT_OUTPUT_DIR", "")
    report_day = 0  # Monday (0 = Monday in Python weekday())
    last_report_date: str | None = None

    def maybe_generate_weekly_report():
        """Auto-generate weekly report every Monday at ~00:00 UTC."""
        nonlocal last_report_date
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        # Only generate on Mondays and not already generated today
        if now.weekday() != report_day or today_str == last_report_date:
            return

        # Only generate between 00:00-00:30 UTC
        if now.hour > 0:
            return

        stats = monitor.get_stats()
        if stats.total_checks == 0:
            return

        last_report_date = today_str
        alert_count = len(alert_manager.get_alert_history())
        report = generate_weekly_report(monitor, hours=168, alert_count=alert_count)

        text_report = format_report_text(report)
        print(text_report)

        # Save to file if output dir is configured
        if report_output_dir:
            os.makedirs(report_output_dir, exist_ok=True)
            filename = f"weekly_report_{today_str}.json"
            filepath = os.path.join(report_output_dir, filename)
            with open(filepath, "w") as f:
                f.write(format_report_json(report))
            print(f"[monitor] Report saved to {filepath}")

            # Also save a text version
            txt_filepath = os.path.join(report_output_dir, f"weekly_report_{today_str}.txt")
            with open(txt_filepath, "w") as f:
                f.write(text_report)
            print(f"[monitor] Text report saved to {txt_filepath}")

        print(f"[monitor] Weekly report generated: {report.status.upper()} | uptime={report.uptime_percentage}% | errors={report.failed_checks}")

    print(f"[monitor] Starting daemon — checking {monitor.base_url} every {monitor.interval_seconds}s")
    print("[monitor] Press Ctrl+C to stop")
    if report_output_dir:
        print(f"[monitor] Weekly reports will be saved to {report_output_dir}")

    # Start initial check
    result = monitor.check_health()
    status = "UP" if result.is_up else "DOWN"
    print(f"[monitor] Initial check: {status} | HTTP {result.status_code} | {result.response_time_ms:.1f}ms")

    # Start background monitoring
    monitor.start()

    # Keep main thread alive with periodic stats and report generation
    try:
        while True:
            time.sleep(300)  # Print stats every 5 minutes
            maybe_generate_weekly_report()
            stats = monitor.get_stats()
            print(
                f"[monitor] Stats: uptime={stats.uptime_percentage}% | "
                f"checks={stats.total_checks} | "
                f"errors={stats.failed_checks} | "
                f"avg={stats.avg_response_time_ms:.1f}ms"
            )
    except KeyboardInterrupt:
        shutdown(None, None)


def run_report(monitor: HealthMonitor) -> None:
    """Generate a weekly report from collected data."""
    # We need some data — collect from history or run fresh checks
    print("[monitor] Generating weekly report...")

    # Check if we have enough history data
    stats = monitor.get_stats()
    if stats.total_checks == 0:
        print("[monitor] No monitoring data available. Run the daemon first to collect data.")
        print("[monitor] Alternatively, run with --once a few times over a period.")
        sys.exit(1)

    alert_manager = create_alert_manager_from_env()
    alert_count = len(alert_manager.get_alert_history())

    report = generate_weekly_report(monitor, hours=168, alert_count=alert_count)
    print(format_report_text(report))


def main():
    parser = argparse.ArgumentParser(description="Halal Check API Monitor")
    parser.add_argument("--once", action="store_true", help="Run a single health check and exit")
    parser.add_argument("--report", action="store_true", help="Generate a weekly report")
    parser.add_argument("--json", action="store_true", help="Output report as JSON (use with --report)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    monitor = create_monitor_from_env()
    alert_manager = create_alert_manager_from_env()

    if args.report:
        run_report(monitor)
    elif args.once:
        run_single_check(monitor, alert_manager)
    else:
        run_daemon(monitor, alert_manager)


if __name__ == "__main__":
    main()
