"""Alert management for deployments and monitoring."""

import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AlertManager:
    """Manage alerts for monitoring and deployment events."""

    def __init__(self, config_path: str = "config/monitoring_config.json"):
        """
        Initialize alert manager.

        Args:
            config_path: Path to monitoring config with alert settings
        """
        self.config_path = config_path
        self.alerts = []

    def add_alert(
        self,
        severity: str,
        title: str,
        message: str,
        details: Dict[str, Any] = None,
    ):
        """
        Add an alert.

        Args:
            severity: INFO, WARNING, or BLOCKER
            title: Alert title
            message: Alert message
            details: Optional details dict
        """
        alert = {
            'timestamp': datetime.utcnow().isoformat(),
            'severity': severity,
            'title': title,
            'message': message,
            'details': details or {},
        }

        self.alerts.append(alert)

        # Log immediately
        level = getattr(logging, severity, logging.INFO)
        logger.log(level, f"{title}: {message}")

        # Send notification (if configured)
        self._send_notification(alert)

    def _send_notification(self, alert: Dict):
        """Send alert via configured channels."""
        # TODO: Implement email, Slack, PagerDuty notifications
        # For now, just log
        logger.info(f"Alert notification: {alert['title']}")

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent alerts."""
        return self.alerts[-limit:]
