"""
Alerting system — handles notifications for API degradation.

Supports:
- Console logging alerts (default)
- Webhook alerts (for Slack, Discord, etc.)
- Email alerts (via SMTP)
- Configurable alert rules (error rate, latency, downtime)
"""

import json
import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """A single alerting rule."""
    name: str
    metric: str  # "error_rate", "latency", "consecutive_failures"
    threshold: float
    comparison: str = "gt"  # "gt", "gte", "lt", "lte", "eq"
    cooldown_minutes: int = 30
    enabled: bool = True
    _last_fired: Optional[datetime] = field(default=None, repr=False)

    def should_fire(self, value: float) -> bool:
        """Check if the rule should fire given the current metric value."""
        if not self.enabled:
            return False

        now = datetime.now(timezone.utc)
        if self._last_fired and (now - self._last_fired).total_seconds() < self.cooldown_minutes * 60:
            return False

        comparisons = {
            "gt": value > self.threshold,
            "gte": value >= self.threshold,
            "lt": value < self.threshold,
            "lte": value <= self.threshold,
            "eq": value == self.threshold,
        }

        if comparisons.get(self.comparison, False):
            self._last_fired = now
            return True

        return False


class ConsoleAlerter:
    """Logs alerts to the console/logger."""

    def send(self, alert_type: str, details: dict) -> None:
        logger.warning("=" * 60)
        logger.warning("  ALERT: %s", alert_type.upper())
        logger.warning("=" * 60)
        for key, value in details.items():
            logger.warning("  %s: %s", key, value)
        logger.warning("=" * 60)


class WebhookAlerter:
    """Sends alerts to a webhook URL (Slack, Discord, generic)."""

    def __init__(self, webhook_url: str, timeout_seconds: float = 10.0):
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def send(self, alert_type: str, details: dict) -> None:
        payload = {
            "text": f"🚨 **Halal Check API Alert**: {alert_type}",
            "alert_type": alert_type,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": "halal-check-api",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.webhook_url, json=payload)
                if response.status_code >= 400:
                    logger.error("Webhook alert failed: HTTP %d - %s", response.status_code, response.text)
                else:
                    logger.info("Webhook alert sent for %s", alert_type)
        except Exception as e:
            logger.error("Failed to send webhook alert: %s", e)


class EmailAlerter:
    """Sends alerts via email (SMTP)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: str = "",
        smtp_password: str = "",
        from_addr: str = "",
        to_addrs: Optional[list[str]] = None,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_addr = from_addr or smtp_user
        self.to_addrs = to_addrs or []
        self.use_tls = use_tls

    def send(self, alert_type: str, details: dict) -> None:
        if not self.to_addrs:
            logger.warning("Email alerter has no recipients configured")
            return

        subject = f"[ALERT] Halal Check API: {alert_type}"
        body = f"""Halal Check API Alert
{'=' * 40}
Alert Type: {alert_type}
Timestamp: {datetime.now(timezone.utc).isoformat()}

Details:
{json.dumps(details, indent=2)}

---
This is an automated alert from Halal Check API monitoring.
"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
                logger.info("Email alert sent to %s for %s", self.to_addrs, alert_type)
        except Exception as e:
            logger.error("Failed to send email alert: %s", e)


class AlertManager:
    """
    Central alert manager that coordinates multiple alert channels
    and evaluates alert rules.
    """

    # Default alert rules per the acceptance criteria
    DEFAULT_RULES = [
        AlertRule(
            name="API Down (consecutive failures >= 3)",
            metric="consecutive_failures",
            threshold=3,
            comparison="gte",
            cooldown_minutes=5,
        ),
        AlertRule(
            name="Error Rate > 5%",
            metric="error_rate",
            threshold=5.0,
            comparison="gt",
            cooldown_minutes=30,
        ),
        AlertRule(
            name="Latency > 2s",
            metric="latency_ms",
            threshold=2000,
            comparison="gt",
            cooldown_minutes=15,
        ),
    ]

    def __init__(self):
        self.alerters: list = []
        self.rules: list[AlertRule] = list(self.DEFAULT_RULES)
        self._alert_history: list[dict] = []

    def add_alerter(self, alerter) -> None:
        """Add an alert channel (ConsoleAlerter, WebhookAlerter, EmailAlerter, etc.)."""
        self.alerters.append(alerter)

    def add_rule(self, rule: AlertRule) -> None:
        """Add a custom alert rule."""
        self.rules.append(rule)

    def evaluate(self, metrics: dict) -> list[dict]:
        """
        Evaluate all rules against current metrics and fire alerts.
        
        Args:
            metrics: Dict with keys like 'consecutive_failures', 'error_rate', 'latency_ms'
        
        Returns:
            List of fired alert details.
        """
        fired_alerts = []

        for rule in self.rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue

            if rule.should_fire(value):
                alert_details = {
                    "rule": rule.name,
                    "metric": rule.metric,
                    "value": value,
                    "threshold": rule.threshold,
                    "comparison": rule.comparison,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "extra_metrics": {k: v for k, v in metrics.items() if k != rule.metric},
                }

                fired_alerts.append(alert_details)
                self._alert_history.append(alert_details)

                # Send through all alerters
                for alerter in self.alerters:
                    try:
                        alerter.send(rule.metric, alert_details)
                    except Exception as e:
                        logger.error("Alerter %s failed: %s", type(alerter).__name__, e)

        return fired_alerts

    def get_alert_history(self, limit: int = 50) -> list[dict]:
        """Get recent alert history."""
        return list(self._alert_history[-limit:])
