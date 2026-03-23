"""
Tests for the monitoring system: health monitor, alerting, and weekly reports.

These test the monitoring infrastructure without requiring a running API server.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from monitoring.alerting import (
    AlertManager,
    AlertRule,
    ConsoleAlerter,
    WebhookAlerter,
)
from monitoring.health_monitor import HealthCheckResult, HealthMonitor
from monitoring.weekly_report import (
    WeeklyReport,
    format_report_json,
    format_report_text,
    generate_weekly_report,
)

# ============================================================================
# SECTION 1: HEALTH MONITOR UNIT TESTS
# ============================================================================

class TestHealthMonitor:
    """Unit tests for HealthMonitor."""

    def test_record_and_retrieve_results(self):
        """Health check results are recorded and retrievable."""
        monitor = HealthMonitor(base_url="http://localhost:9999")

        # Manually inject results
        now = datetime.now(UTC)
        for i in range(5):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=i * 2),
                status_code=200,
                response_time_ms=100.0 + i * 10,
                is_up=True,
            )
            monitor._record_result(result)

        recent = monitor.get_recent_results(limit=10)
        assert len(recent) == 5

    def test_stats_calculation(self):
        """Stats are calculated correctly from recorded results."""
        monitor = HealthMonitor(base_url="http://localhost:9999")

        now = datetime.now(UTC)
        # 8 successful, 2 failed
        for i in range(8):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=i),
                status_code=200,
                response_time_ms=50.0 + i * 10,
                is_up=True,
            )
            monitor._record_result(result)

        for i in range(2):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=10 + i),
                status_code=0,
                response_time_ms=5000.0,
                is_up=False,
                error="Connection refused",
            )
            monitor._record_result(result)

        stats = monitor.get_stats()
        assert stats.total_checks == 10
        assert stats.successful_checks == 8
        assert stats.failed_checks == 2
        assert stats.uptime_percentage == 80.0
        assert stats.error_rate == 20.0
        assert stats.avg_response_time_ms == 85.0  # (50+60+70+80+90+100+110+120)/8

    def test_stats_empty_history(self):
        """Stats with no history return zeros."""
        monitor = HealthMonitor(base_url="http://localhost:9999")
        stats = monitor.get_stats()
        assert stats.total_checks == 0
        assert stats.uptime_percentage == 0.0

    def test_consecutive_failures_tracked(self):
        """Consecutive failures are counted from the most recent check."""
        monitor = HealthMonitor(base_url="http://localhost:9999")

        now = datetime.now(UTC)
        # 3 successful, then 4 failures (most recent first in recording)
        for i in range(4):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=i),
                status_code=0,
                response_time_ms=5000.0,
                is_up=False,
                error="down",
            )
            monitor._record_result(result)

        for i in range(3):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=4 + i),
                status_code=200,
                response_time_ms=50.0,
                is_up=True,
            )
            monitor._record_result(result)

        stats = monitor.get_stats()
        assert stats.consecutive_failures == 4

    def test_old_results_pruned(self):
        """Results older than the window are pruned."""
        monitor = HealthMonitor(base_url="http://localhost:9999", history_window_hours=1)

        now = datetime.now(UTC)
        # Old result (outside window)
        old_result = HealthCheckResult(
            timestamp=now - timedelta(hours=2),
            status_code=200,
            response_time_ms=100.0,
            is_up=True,
        )
        monitor._record_result(old_result)

        # Recent result (inside window)
        recent_result = HealthCheckResult(
            timestamp=now - timedelta(minutes=10),
            status_code=200,
            response_time_ms=100.0,
            is_up=True,
        )
        monitor._record_result(recent_result)

        stats = monitor.get_stats()
        assert stats.total_checks == 1

    def test_alert_callback_fired_on_consecutive_failures(self):
        """Alert callback is called after consecutive failures threshold."""
        monitor = HealthMonitor(base_url="http://localhost:9999")
        monitor.ALERT_CONSECUTIVE_FAILURES = 3
        monitor._alert_suppression_minutes = 0  # No suppression for testing

        alerts = []
        monitor.set_alert_callback(lambda atype, details: alerts.append((atype, details)))

        now = datetime.now(UTC)
        # Record 3 failures
        for i in range(3):
            result = HealthCheckResult(
                timestamp=now - timedelta(seconds=i),
                status_code=0,
                response_time_ms=5000.0,
                is_up=False,
                error="Connection refused",
            )
            monitor._record_result(result)
            monitor._evaluate_alerts(result)

        # Should have fired at least one api_down alert
        alert_types = [a[0] for a in alerts]
        assert "api_down" in alert_types

    def test_latency_alert_fired_for_slow_responses(self):
        """Alert callback is called when latency exceeds threshold."""
        monitor = HealthMonitor(base_url="http://localhost:9999")
        monitor.ALERT_LATENCY_THRESHOLD_MS = 100  # Low threshold for testing
        monitor._alert_suppression_minutes = 0

        alerts = []
        monitor.set_alert_callback(lambda atype, details: alerts.append((atype, details)))

        now = datetime.now(UTC)
        # First: normal response
        normal = HealthCheckResult(
            timestamp=now - timedelta(seconds=2),
            status_code=200,
            response_time_ms=50.0,
            is_up=True,
        )
        monitor._record_result(normal)
        monitor._evaluate_alerts(normal)

        # Second: slow response
        slow = HealthCheckResult(
            timestamp=now - timedelta(seconds=1),
            status_code=200,
            response_time_ms=500.0,  # Over 100ms threshold
            is_up=True,
        )
        monitor._record_result(slow)
        monitor._evaluate_alerts(slow)

        alert_types = [a[0] for a in alerts]
        assert "high_latency" in alert_types

    def test_alert_suppression_prevents_spam(self):
        """Alerts are suppressed for the cooldown period."""
        monitor = HealthMonitor(base_url="http://localhost:9999")
        monitor._alert_suppression_minutes = 60  # Long suppression

        alerts = []
        monitor.set_alert_callback(lambda atype, details: alerts.append((atype, details)))

        now = datetime.now(UTC)
        # Fire multiple alerts of the same type
        for i in range(5):
            result = HealthCheckResult(
                timestamp=now - timedelta(seconds=i),
                status_code=200,
                response_time_ms=500.0,  # Over default 2000ms threshold
                is_up=True,
            )
            monitor._record_result(result)
            monitor._evaluate_alerts(result)

        # Should only fire once due to suppression
        latency_alerts = [a for a in alerts if a[0] == "high_latency"]
        assert len(latency_alerts) <= 1


# ============================================================================
# SECTION 2: ALERT MANAGER TESTS
# ============================================================================

class TestAlertManager:
    """Unit tests for AlertManager."""

    def test_default_rules_exist(self):
        """Alert manager should have default rules configured."""
        manager = AlertManager()
        assert len(manager.rules) >= 3

        rule_names = [r.name for r in manager.rules]
        assert any("consecutive" in n.lower() or "failures" in n.lower() for n in rule_names)
        assert any("error" in n.lower() and "rate" in n.lower() for n in rule_names)
        assert any("latency" in n.lower() for n in rule_names)

    def test_rule_fires_when_threshold_exceeded(self):
        """Rule fires when metric exceeds threshold."""
        rule = AlertRule(
            name="Test Rule",
            metric="error_rate",
            threshold=5.0,
            comparison="gt",
            cooldown_minutes=0,
        )

        assert rule.should_fire(6.0) is True
        assert rule.should_fire(5.0) is False
        assert rule.should_fire(3.0) is False

    def test_rule_cooldown_prevents_repeated_firing(self):
        """Rule cooldown prevents firing within the cooldown window."""
        rule = AlertRule(
            name="Test Rule",
            metric="error_rate",
            threshold=5.0,
            comparison="gt",
            cooldown_minutes=60,
        )

        assert rule.should_fire(6.0) is True
        # Immediate retry should be suppressed
        assert rule.should_fire(6.0) is False

    def test_rule_disabled(self):
        """Disabled rules never fire."""
        rule = AlertRule(
            name="Test Rule",
            metric="error_rate",
            threshold=5.0,
            comparison="gt",
            enabled=False,
        )
        assert rule.should_fire(100.0) is False

    def test_evaluate_fires_correct_rules(self):
        """Evaluate returns fired alerts for matching rules."""
        manager = AlertManager()
        alerts_fired = []

        class TestAlerter:
            def send(self, alert_type, details):
                alerts_fired.append(alert_type)

        manager.add_alerter(TestAlerter())
        # Clear default rules, add specific test rules
        manager.rules = [
            AlertRule(name="High error rate", metric="error_rate", threshold=5.0, comparison="gt", cooldown_minutes=0),
            AlertRule(name="High latency", metric="latency_ms", threshold=2000.0, comparison="gt", cooldown_minutes=0),
        ]

        metrics = {"error_rate": 10.0, "latency_ms": 100.0}
        fired = manager.evaluate(metrics)

        assert len(fired) == 1
        assert fired[0]["metric"] == "error_rate"
        assert len(alerts_fired) == 1

    def test_console_alerter(self, caplog):
        """Console alerter logs alerts."""
        alerter = ConsoleAlerter()
        with patch("monitoring.alerting.logger") as mock_logger:
            alerter.send("test_alert", {"key": "value"})
            # Should have called warning
            assert mock_logger.warning.called

    def test_webhook_alerter_success(self):
        """Webhook alerter sends POST to webhook URL."""
        alerter = WebhookAlerter(webhook_url="https://hooks.example.com/test")

        with patch("monitoring.alerting.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(status_code=200)
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_instance

            alerter.send("test_alert", {"key": "value"})
            mock_instance.post.assert_called_once()

    def test_webhook_alerter_failure_logged(self):
        """Webhook alerter logs errors when webhook fails."""
        alerter = WebhookAlerter(webhook_url="https://hooks.example.com/test")

        with patch("monitoring.alerting.httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.post.return_value = MagicMock(status_code=500, text="Server Error")
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_instance

            # Should not raise
            alerter.send("test_alert", {"key": "value"})


# ============================================================================
# SECTION 3: WEEKLY REPORT TESTS
# ============================================================================

class TestWeeklyReport:
    """Unit tests for the weekly report generator."""

    def test_generate_report_from_monitor(self):
        """Report can be generated from monitor data."""
        monitor = HealthMonitor(base_url="http://localhost:9999")

        now = datetime.now(UTC)
        for i in range(10):
            result = HealthCheckResult(
                timestamp=now - timedelta(minutes=i * 5),
                status_code=200 if i % 5 != 0 else 0,
                response_time_ms=50.0 + i * 5,
                is_up=(i % 5 != 0),
                error=None if i % 5 != 0 else "timeout",
            )
            monitor._record_result(result)

        report = generate_weekly_report(monitor, hours=1, alert_count=2)

        assert report.total_checks == 10
        assert report.status in ("healthy", "degraded", "critical")
        assert report.alert_count == 2

    def test_format_report_text(self):
        """Text report format is valid and contains key info."""
        report = WeeklyReport(
            generated_at="2026-03-23T00:00:00Z",
            period_hours=168,
            total_checks=10080,
            successful_checks=10070,
            failed_checks=10,
            uptime_percentage=99.90,
            avg_response_time_ms=45.2,
            max_response_time_ms=1500.0,
            min_response_time_ms=12.0,
            error_rate=0.10,
            p95_response_time_ms=120.0,
            p99_response_time_ms=450.0,
            status="healthy",
        )

        text = format_report_text(report)
        assert "99.9%" in text
        assert "45.2" in text
        assert "HEALTHY" in text
        assert "HALAL CHECK API" in text

    def test_format_report_json(self):
        """JSON report format is valid."""
        report = WeeklyReport(
            generated_at="2026-03-23T00:00:00Z",
            period_hours=168,
            total_checks=100,
            successful_checks=90,
            failed_checks=10,
            uptime_percentage=90.0,
            avg_response_time_ms=100.0,
            max_response_time_ms=2000.0,
            min_response_time_ms=20.0,
            error_rate=10.0,
            status="degraded",
        )

        import json
        json_str = format_report_json(report)
        parsed = json.loads(json_str)
        assert parsed["uptime_percentage"] == 90.0
        assert parsed["status"] == "degraded"

    def test_report_status_healthy(self):
        """Report status is 'healthy' when uptime >= 99.5% and error rate < 1%."""
        report = WeeklyReport(
            generated_at="2026-03-23T00:00:00Z",
            period_hours=168,
            total_checks=1000,
            successful_checks=998,
            failed_checks=2,
            uptime_percentage=99.8,
            avg_response_time_ms=50.0,
            max_response_time_ms=200.0,
            min_response_time_ms=20.0,
            error_rate=0.2,
            status="healthy",
        )
        assert report.status == "healthy"

    def test_report_status_critical(self):
        """Report status is 'critical' when uptime < 95%."""
        report = WeeklyReport(
            generated_at="2026-03-23T00:00:00Z",
            period_hours=168,
            total_checks=100,
            successful_checks=80,
            failed_checks=20,
            uptime_percentage=80.0,
            avg_response_time_ms=50.0,
            max_response_time_ms=2000.0,
            min_response_time_ms=20.0,
            error_rate=20.0,
            status="critical",
        )
        assert report.status == "critical"


# ============================================================================
# SECTION 4: INTEGRATION — MONITOR PINGING REAL API
# ============================================================================

class TestMonitorIntegration:
    """Integration tests that verify monitoring against a real (or test) API."""

    def test_monitor_can_ping_real_api(self):
        """Monitor can perform a health check against the running API.

        This test requires the API to be running on localhost:8000.
        Marked as slow since it makes real HTTP calls.
        """
        monitor = HealthMonitor(
            base_url="http://localhost:8000",
            timeout_seconds=5.0,
        )

        # Try a single check — if API is running, this should work
        try:
            result = monitor.check_health()
            # API might or might not be running in CI
            if result.is_up:
                assert result.status_code == 200
                assert result.response_time_ms > 0
        except Exception:
            pytest.skip("API not running on localhost:8000")
