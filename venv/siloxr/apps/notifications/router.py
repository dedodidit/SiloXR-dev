# backend/apps/notifications/router.py

"""
Notification Router.

Central dispatcher that decides which channels to use
for a given decision/insight based on:
  - user's preferred_channel preference
  - decision confidence and severity
  - per-channel throttle state

Routing rules:

ALL USERS:
  → Always: in-app notification
  → Email when the address is present and notifications are enabled

WhatsApp is temporarily disabled and handled elsewhere in the product.

This module replaces direct calls to dispatch.py for routing decisions.
dispatch.py remains for the actual sending logic.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REMINDER_THROTTLE_CHANNEL = "upd_reminder"


@dataclass
class RoutingResult:
    """Which channels were attempted and whether they succeeded."""
    in_app: bool = False
    whatsapp: bool = False
    email: bool = False
    skipped: list = None

    def __post_init__(self):
        if self.skipped is None:
            self.skipped = []

    @property
    def any_delivered(self) -> bool:
        return any([self.in_app, self.whatsapp, self.email])


class NotificationRouter:
    """
    Routes a notification to appropriate channels.
    Called from apps/notifications/dispatch.py.
    """

    def route_decision(self, decision, product) -> RoutingResult:
        from apps.notifications.dispatch import _build_title, _build_body, _send_email, record_channel_delivery
        from apps.notifications.models import Notification

        user = product.owner
        result = RoutingResult()

        title = _build_title(decision)
        body = _build_body(decision)

        Notification.objects.create(
            user=user,
            decision=decision,
            channel=Notification.CHANNEL_IN_APP,
            title=title,
            body=body,
            confidence=decision.confidence_score,
        )
        result.in_app = True

        if self._should_email(user):
            try:
                if _send_email(user, decision, title, body):
                    result.email = True
                    record_channel_delivery(user, Notification.CHANNEL_EMAIL, title, body, decision.confidence_score, decision)
                else:
                    result.skipped.append("email")
            except Exception as exc:
                logger.error("Email routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        logger.info(
            "Notification routed for %s [%s]: in_app=%s whatsapp=%s email=%s",
            product.sku, decision.action,
            result.in_app, result.whatsapp, result.email,
        )
        return result

    def route_insight(self, user, product, insight) -> RoutingResult:
        from apps.notifications.dispatch import _build_insight_email_html, _dashboard_url, _send_email_message, record_channel_delivery
        from apps.notifications.models import Notification

        result = RoutingResult()
        title = getattr(insight, "title", "") or getattr(insight, "observation", "") or f"Insight: {product.name}"
        body = getattr(insight, "message", "") or getattr(insight, "reasoning", "") or ""
        confidence = float(getattr(insight, "confidence", 0.5) or 0.5)

        if not body:
            return result

        Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            title=title[:255],
            body=body,
            confidence=confidence,
        )
        result.in_app = True

        if self._should_email(user):
            try:
                email_body = f"{title}\n\n{body}"
                dashboard_url = _dashboard_url("/dashboard")
                if dashboard_url:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                html = _build_insight_email_html(user, title[:255], body, "/dashboard")
                if _send_email_message(user, title[:255], email_body, html):
                    result.email = True
                    record_channel_delivery(user, Notification.CHANNEL_EMAIL, title[:255], email_body, confidence)
                else:
                    result.skipped.append("email")
            except Exception as exc:
                logger.error("Email insight routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_dashboard_insight(self, user, insight) -> RoutingResult:
        from apps.notifications.dispatch import _build_insight_email_html, _dashboard_url, _send_email_message, record_channel_delivery
        from apps.notifications.models import Notification

        result = RoutingResult()
        title = (insight or {}).get("title", "") or "Dashboard insight"
        body = (insight or {}).get("body", "") or (insight or {}).get("message", "")
        confidence = float((insight or {}).get("confidence", 0.55) or 0.55)
        dashboard_path = (insight or {}).get("dashboard_path", "/dashboard")

        if not body:
            return result

        Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            title=title[:255],
            body=body,
            confidence=confidence,
        )
        result.in_app = True

        if self._should_email(user):
            try:
                email_body = f"{title}\n\n{body}"
                dashboard_url = _dashboard_url(dashboard_path)
                if dashboard_url:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                html = _build_insight_email_html(user, title[:255], body, dashboard_path)
                if _send_email_message(user, title[:255], email_body, html):
                    result.email = True
                    record_channel_delivery(user, Notification.CHANNEL_EMAIL, title[:255], email_body, confidence)
                else:
                    result.skipped.append("email")
            except Exception as exc:
                logger.error("Email dashboard insight routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_dashboard_brief(self, user, insight) -> RoutingResult:
        from apps.notifications.dispatch import _dashboard_url, _send_email_message, record_channel_delivery
        from apps.notifications.models import Notification

        result = RoutingResult()
        title = (insight or {}).get("title", "") or "Business brief"
        body = (insight or {}).get("body", "") or ""
        html = (insight or {}).get("html")
        confidence = float((insight or {}).get("confidence", 0.62) or 0.62)
        dashboard_path = (insight or {}).get("dashboard_path", "/dashboard")

        if not body:
            return result

        Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            title=title[:255],
            body=body,
            confidence=confidence,
        )
        result.in_app = True

        if self._should_email(user):
            try:
                email_body = body
                dashboard_url = _dashboard_url(dashboard_path)
                if dashboard_url and dashboard_url not in email_body:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                if _send_email_message(user, title[:255], email_body, html):
                    result.email = True
                    record_channel_delivery(user, Notification.CHANNEL_EMAIL, title[:255], email_body, confidence)
                else:
                    result.skipped.append("email")
            except Exception as exc:
                logger.error("Email dashboard brief routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_product_update_reminder(self, user, products, cadence_hours: int = 24) -> RoutingResult:
        from apps.notifications.dispatch import (
            _build_product_update_body,
            _build_product_update_email_html,
            _build_product_update_title,
            _send_email_message,
            record_channel_delivery,
        )
        from apps.notifications.models import Notification, NotificationThrottle

        result = RoutingResult()
        products = list(products or [])
        if not products:
            return result

        throttle = NotificationThrottle.objects.filter(
            user=user,
            product=None,
            channel=REMINDER_THROTTLE_CHANNEL,
        ).first()
        if throttle and throttle.is_throttled(cadence_hours, 1):
            result.skipped.append("cadence")
            return result

        title = _build_product_update_title(products)
        body = _build_product_update_body(products)
        html = _build_product_update_email_html(user, products, title, body)

        Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            title=title[:255],
            body=body,
            confidence=0.4,
        )
        result.in_app = True

        if self._should_email(user):
            try:
                if _send_email_message(user, title[:255], body, html):
                    result.email = True
                    record_channel_delivery(user, Notification.CHANNEL_EMAIL, title[:255], body, 0.4)
                else:
                    result.skipped.append("email")
            except Exception as exc:
                logger.error("Email reminder routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        if result.any_delivered:
            NotificationThrottle.record(user, None, REMINDER_THROTTLE_CHANNEL)

        return result

    def _should_email(self, user) -> bool:
        if not getattr(user, "email", "") or not getattr(user, "email_notifications_enabled", True):
            return False
        return True
