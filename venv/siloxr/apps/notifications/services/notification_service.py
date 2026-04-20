from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from html import escape

from django.utils import timezone

from apps.notifications.models import Notification


SEVERITY_ORDER = {
    Notification.SEVERITY_LOW: 1,
    Notification.SEVERITY_MEDIUM: 2,
    Notification.SEVERITY_HIGH: 3,
    Notification.SEVERITY_CRITICAL: 4,
}


def _normalize_severity(value: str | None) -> str:
    severity = (value or Notification.SEVERITY_MEDIUM).strip().lower()
    return severity if severity in SEVERITY_ORDER else Notification.SEVERITY_MEDIUM


def _severity_confidence(severity: str) -> float:
    return {
        Notification.SEVERITY_LOW: 0.35,
        Notification.SEVERITY_MEDIUM: 0.55,
        Notification.SEVERITY_HIGH: 0.75,
        Notification.SEVERITY_CRITICAL: 0.9,
    }.get(severity, 0.5)


def _default_title(notification_type: str) -> str:
    label = (notification_type or Notification.TYPE_GENERIC).replace("_", " ").strip()
    if not label:
        label = "notification"
    return label.title()


@dataclass
class NotificationDispatchResult:
    notification: Notification | None
    created: bool
    delivered_email: bool = False
    skipped_reason: str = ""


class NotificationService:
    """
    Stores a logical notification in the database and optionally delivers
    it through currently supported channels.

    Dedupe rule:
    - same user + notification_type + reference_id within 24 hours
    - newer higher-severity notifications are allowed to escalate
    """

    dedupe_window = timedelta(hours=24)

    def send_notification(
        self,
        user,
        message: str,
        notification_type: str,
        reference_id: str | None = None,
        *,
        severity: str = Notification.SEVERITY_MEDIUM,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationDispatchResult:
        severity = _normalize_severity(severity)
        reference_key = str(reference_id or "").strip()
        title = (title or _default_title(notification_type))[:255]
        message = (message or "").strip()
        if not message:
            return NotificationDispatchResult(
                notification=None,
                created=False,
                skipped_reason="empty_message",
            )

        if self._is_duplicate(user, notification_type, reference_key, severity):
            existing = self._latest_notification(user, notification_type, reference_key)
            return NotificationDispatchResult(
                notification=existing,
                created=False,
                skipped_reason="duplicate",
            )

        notification = Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            notification_type=notification_type or Notification.TYPE_GENERIC,
            reference_id=reference_key,
            severity=severity,
            payload=metadata or {},
            title=title,
            body=message,
            confidence=_severity_confidence(severity),
        )

        return NotificationDispatchResult(notification=notification, created=True)

    def notify_user(
        self,
        user,
        message: str,
        notification_type: str,
        reference_id: str | None = None,
        *,
        severity: str = Notification.SEVERITY_MEDIUM,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
        send_email: bool = True,
        dashboard_path: str = "/dashboard",
    ) -> NotificationDispatchResult:
        result = self.send_notification(
            user,
            message,
            notification_type,
            reference_id,
            severity=severity,
            title=title,
            metadata=metadata,
        )

        if not result.created or not send_email or result.notification is None:
            return result

        delivered = self.deliver_email(
            result.notification,
            dashboard_path=dashboard_path,
        )
        result.delivered_email = delivered
        return result

    def deliver_email(
        self,
        notification: Notification,
        *,
        dashboard_path: str = "/dashboard",
    ) -> bool:
        user = notification.user
        if not getattr(user, "email", ""):
            return False
        if not getattr(user, "email_notifications_enabled", True):
            return False

        from apps.notifications.dispatch import _build_cta_html, _dashboard_url, _send_email_message

        dashboard_url = _dashboard_url(dashboard_path)
        cta = _build_cta_html("Open dashboard", dashboard_url) if dashboard_url else ""
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #141412;">
            <h2 style="margin-bottom: 8px;">{escape(notification.title)}</h2>
            <p style="margin: 0 0 12px;">Hi {escape(user.first_name or user.username or 'there')},</p>
            <p style="margin: 0 0 12px; white-space: pre-line;">{escape(notification.body)}</p>
            {cta}
          </body>
        </html>
        """
        body = notification.body
        if dashboard_url:
            body = f"{body}\n\nOpen dashboard: {dashboard_url}"
        return _send_email_message(user, notification.title, body, html)

    def _latest_notification(
        self,
        user,
        notification_type: str,
        reference_id: str,
    ) -> Notification | None:
        return (
            Notification.objects.filter(
                user=user,
                notification_type=notification_type or Notification.TYPE_GENERIC,
                reference_id=reference_id,
                created_at__gte=timezone.now() - self.dedupe_window,
            )
            .order_by("-created_at")
            .first()
        )

    def _is_duplicate(
        self,
        user,
        notification_type: str,
        reference_id: str,
        severity: str,
    ) -> bool:
        latest = self._latest_notification(user, notification_type, reference_id)
        if latest is None:
            return False
        latest_rank = SEVERITY_ORDER.get(_normalize_severity(getattr(latest, "severity", "")), 2)
        current_rank = SEVERITY_ORDER.get(severity, 2)
        return latest_rank >= current_rank


def send_notification(
    user,
    message: str,
    notification_type: str,
    reference_id: str | None = None,
    *,
    severity: str = Notification.SEVERITY_MEDIUM,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> NotificationDispatchResult:
    return NotificationService().send_notification(
        user,
        message,
        notification_type,
        reference_id,
        severity=severity,
        title=title,
        metadata=metadata,
    )


def notify_user(
    user,
    message: str,
    notification_type: str,
    reference_id: str | None = None,
    *,
    severity: str = Notification.SEVERITY_MEDIUM,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
    send_email: bool = True,
    dashboard_path: str = "/dashboard",
) -> NotificationDispatchResult:
    return NotificationService().notify_user(
        user,
        message,
        notification_type,
        reference_id,
        severity=severity,
        title=title,
        metadata=metadata,
        send_email=send_email,
        dashboard_path=dashboard_path,
    )
