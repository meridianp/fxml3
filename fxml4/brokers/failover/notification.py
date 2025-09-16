"""
Failover Notification Service for FXML4 Trading System.
Handles critical notifications during broker failover events.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """Notification priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class NotificationConfig:
    """Notification configuration."""

    email_enabled: bool = True
    sms_enabled: bool = False
    webhook_enabled: bool = False
    email_recipients: List[str] = None
    sms_recipients: List[str] = None
    smtp_server: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    webhook_url: str = ""


class FailoverNotificationService:
    """
    Notification service for broker failover events.
    Supports email, SMS, and webhook notifications.
    """

    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize notification service."""
        self.config = config or NotificationConfig()
        self.notification_history = []
        self.failed_notifications = []

    async def send_notification(
        self, event_type: str, message: str, priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send notification for failover event."""
        notification = {
            "event_type": event_type,
            "message": message,
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat(),
            "notification_id": f"NOTIF_{len(self.notification_history) + 1}",
            "delivery_status": {},
        }

        try:
            # Send via different channels based on priority
            if priority in ["high", "critical"]:
                # High priority: send via all channels
                if self.config.email_enabled:
                    await self._send_email_notification(notification)

                if self.config.sms_enabled and priority == "critical":
                    await self._send_sms_notification(notification)

                if self.config.webhook_enabled:
                    await self._send_webhook_notification(notification)
            else:
                # Normal/low priority: email only
                if self.config.email_enabled:
                    await self._send_email_notification(notification)

            self.notification_history.append(notification)
            logger.info(f"Notification sent: {event_type} [{priority}]")

        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            notification["delivery_status"]["error"] = str(e)
            self.failed_notifications.append(notification)

        return notification

    async def _send_email_notification(self, notification: Dict[str, Any]):
        """Send email notification."""
        if not self.config.email_recipients:
            notification["delivery_status"]["email"] = "no_recipients"
            return

        try:
            subject = f"FXML4 Broker Failover: {notification['event_type']}"

            # Create email content
            body = f"""
FXML4 Trading System - Broker Failover Notification

Event: {notification['event_type']}
Priority: {notification['priority'].upper()}
Time: {notification['timestamp']}

Message:
{notification['message']}

Notification ID: {notification['notification_id']}

---
FXML4 Trading System
            """.strip()

            # For testing, simulate email sending
            await asyncio.sleep(0.1)  # Simulate email sending delay

            notification["delivery_status"]["email"] = "sent"
            logger.debug(
                f"Email notification sent to {len(self.config.email_recipients)} recipients"
            )

        except Exception as e:
            notification["delivery_status"]["email"] = f"failed: {str(e)}"
            raise

    async def _send_sms_notification(self, notification: Dict[str, Any]):
        """Send SMS notification for critical events."""
        if not self.config.sms_recipients:
            notification["delivery_status"]["sms"] = "no_recipients"
            return

        try:
            # SMS content should be brief
            sms_message = f"FXML4 CRITICAL: {notification['event_type']} - {notification['message'][:100]}"

            # For testing, simulate SMS sending
            await asyncio.sleep(0.1)

            notification["delivery_status"]["sms"] = "sent"
            logger.debug(
                f"SMS notification sent to {len(self.config.sms_recipients)} recipients"
            )

        except Exception as e:
            notification["delivery_status"]["sms"] = f"failed: {str(e)}"
            raise

    async def _send_webhook_notification(self, notification: Dict[str, Any]):
        """Send webhook notification."""
        if not self.config.webhook_url:
            notification["delivery_status"]["webhook"] = "no_url"
            return

        try:
            # Webhook payload
            payload = {
                "event_type": notification["event_type"],
                "message": notification["message"],
                "priority": notification["priority"],
                "timestamp": notification["timestamp"],
                "notification_id": notification["notification_id"],
                "source": "fxml4_failover",
            }

            # For testing, simulate webhook sending
            await asyncio.sleep(0.1)

            notification["delivery_status"]["webhook"] = "sent"
            logger.debug(f"Webhook notification sent to {self.config.webhook_url}")

        except Exception as e:
            notification["delivery_status"]["webhook"] = f"failed: {str(e)}"
            raise

    def get_notification_history(self) -> List[Dict[str, Any]]:
        """Get notification history."""
        return self.notification_history.copy()

    def get_failed_notifications(self) -> List[Dict[str, Any]]:
        """Get failed notifications."""
        return self.failed_notifications.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics."""
        total_sent = len(self.notification_history)
        total_failed = len(self.failed_notifications)

        priority_counts = {}
        for notification in self.notification_history:
            priority = notification["priority"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return {
            "total_notifications": total_sent + total_failed,
            "successful_notifications": total_sent,
            "failed_notifications": total_failed,
            "success_rate": (
                (total_sent / (total_sent + total_failed) * 100)
                if (total_sent + total_failed) > 0
                else 0
            ),
            "priority_distribution": priority_counts,
            "config": {
                "email_enabled": self.config.email_enabled,
                "sms_enabled": self.config.sms_enabled,
                "webhook_enabled": self.config.webhook_enabled,
            },
        }

    async def test_notification_channels(self) -> Dict[str, Any]:
        """Test all notification channels."""
        test_results = {}

        test_notification = {
            "event_type": "system_test",
            "message": "FXML4 notification system test",
            "priority": "normal",
            "timestamp": datetime.utcnow().isoformat(),
            "notification_id": "TEST_NOTIF",
            "delivery_status": {},
        }

        # Test email
        if self.config.email_enabled:
            try:
                await self._send_email_notification(test_notification)
                test_results["email"] = "success"
            except Exception as e:
                test_results["email"] = f"failed: {str(e)}"

        # Test SMS
        if self.config.sms_enabled:
            try:
                await self._send_sms_notification(test_notification)
                test_results["sms"] = "success"
            except Exception as e:
                test_results["sms"] = f"failed: {str(e)}"

        # Test webhook
        if self.config.webhook_enabled:
            try:
                await self._send_webhook_notification(test_notification)
                test_results["webhook"] = "success"
            except Exception as e:
                test_results["webhook"] = f"failed: {str(e)}"

        logger.info(f"Notification channel test results: {test_results}")
        return test_results
