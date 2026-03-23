# backend/apps/notifications/router.py

"""
Notification Router.

Central dispatcher that decides which channels to use
for a given decision/insight based on:
  - user tier (free vs pro)
  - user's preferred_channel preference
  - decision confidence and severity
  - per-channel throttle state

Routing rules:

FREE USERS:
  → Always: in-app notification
  → If preferred_channel = telegram AND telegram linked: Telegram
  → Else: email (daily digest, not real-time)

PRO USERS:
  → Always: in-app notification
  → WhatsApp IF:
      confidence > 0.7
      severity in {critical, warning}
      NOT throttled (1/product/day, 6h cooldown)
      NOT whatsapp_critical_only OR action = ALERT_CRITICAL
  → Telegram if linked (regardless of tier)
  → Email fallback if no other channel delivered

This module replaces direct calls to dispatch.py for routing decisions.
dispatch.py remains for the actual sending logic.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

REMINDER_THROTTLE_CHANNEL = "upd_reminder"


@dataclass
class RoutingResult:
    """Which channels were attempted and whether they succeeded."""
    in_app:    bool = False
    telegram:  bool = False
    whatsapp:  bool = False
    email:     bool = False
    skipped:   list = None

    def __post_init__(self):
        if self.skipped is None:
            self.skipped = []

    @property
    def any_delivered(self) -> bool:
        return any([self.in_app, self.telegram, self.whatsapp, self.email])


class NotificationRouter:
    """
    Routes a decision notification to appropriate channels.
    Called from apps/notifications/dispatch.py.
    """

    def route_decision(self, decision, product) -> RoutingResult:
        """
        Route a DecisionLog to all appropriate channels.
        Returns RoutingResult with delivery status per channel.
        """
        from apps.notifications.dispatch import _build_title, _build_body, _send_email
        from apps.notifications.models import Notification

        user   = product.owner
        result = RoutingResult()

        title = _build_title(decision)
        body  = _build_body(decision)

        # ── 1. Always: in-app ────────────────────────────────────────────
        Notification.objects.create(
            user       = user,
            decision   = decision,
            channel    = Notification.CHANNEL_IN_APP,
            title      = title,
            body       = body,
            confidence = decision.confidence_score,
        )
        result.in_app = True

        # ── 2. Telegram (free + pro, if linked) ──────────────────────────
        if self._should_telegram(user, decision):
            try:
                from apps.notifications.telegram import send_decision_alert
                from apps.notifications.models import TelegramProfile
                profile = user.telegram_profile
                if send_decision_alert(profile.chat_id, decision, product):
                    result.telegram = True
                    logger.info("Telegram delivered for %s → %s", user.username, decision.action)
            except Exception as exc:
                logger.error("Telegram routing error: %s", exc, exc_info=True)
                result.skipped.append("telegram")

        # WhatsApp is temporarily disabled.
        # ── 3. Email (fallback or primary channel) ───────────────────────
        if self._should_email(user, decision, result):
            try:
                _send_email(user, decision, title, body)
                result.email = True
            except Exception as exc:
                logger.error("Email routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        logger.info(
            "Notification routed for %s [%s]: in_app=%s telegram=%s whatsapp=%s email=%s",
            product.sku, decision.action,
            result.in_app, result.telegram, result.whatsapp, result.email,
        )
        return result

    def route_insight(self, user, product, insight) -> RoutingResult:
        """
        Route a non-decision insight through the user's active notification
        preferences while always keeping an in-app record.
        """
        from apps.notifications.dispatch import _build_insight_email_html, _dashboard_url, _send_email_message
        from apps.notifications.models import Notification
        from apps.notifications.telegram import send_insight

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

        if self._should_telegram(user, None):
            try:
                profile = user.telegram_profile
                if send_insight(
                    profile.chat_id,
                    {
                        "title": title,
                        "reasoning": body,
                        "confidence": confidence,
                        "product_name": product.name,
                        "date_signal": getattr(insight, "date_signal", ""),
                    },
                ):
                    result.telegram = True
            except Exception as exc:
                logger.error("Telegram insight routing error: %s", exc, exc_info=True)
                result.skipped.append("telegram")

        if self._should_email(user, None, result):
            try:
                email_body = f"{title}\n\n{body}"
                dashboard_url = _dashboard_url("/dashboard")
                if dashboard_url:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                html = _build_insight_email_html(user, title[:255], body, "/dashboard")
                _send_email_message(user, title[:255], email_body, html)
                result.email = True
            except Exception as exc:
                logger.error("Email insight routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_dashboard_insight(self, user, insight) -> RoutingResult:
        """
        Route dashboard-derived insights that are not tied to a single product.
        """
        from apps.notifications.dispatch import _build_insight_email_html, _dashboard_url, _send_email_message
        from apps.notifications.models import Notification
        from apps.notifications.telegram import send_insight

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

        if self._should_telegram(user, None):
            try:
                profile = user.telegram_profile
                if send_insight(
                    profile.chat_id,
                    {
                        "title": title,
                        "reasoning": body,
                        "confidence": confidence,
                        "product_name": "",
                        "date_signal": "",
                    },
                ):
                    result.telegram = True
            except Exception as exc:
                logger.error("Telegram dashboard insight routing error: %s", exc, exc_info=True)
                result.skipped.append("telegram")

        if self._should_email(user, None, result):
            try:
                email_body = f"{title}\n\n{body}"
                dashboard_url = _dashboard_url(dashboard_path)
                if dashboard_url:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                html = _build_insight_email_html(user, title[:255], body, dashboard_path)
                _send_email_message(user, title[:255], email_body, html)
                result.email = True
            except Exception as exc:
                logger.error("Email dashboard insight routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_dashboard_brief(self, user, insight) -> RoutingResult:
        """
        Route a grouped start/end-of-business dashboard brief.
        """
        from apps.notifications.dispatch import _dashboard_url, _send_email_message
        from apps.notifications.models import Notification
        from apps.notifications.telegram import send_insight

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

        if self._should_telegram(user, None):
            try:
                profile = user.telegram_profile
                if send_insight(
                    profile.chat_id,
                    {
                        "title": title,
                        "reasoning": body,
                        "confidence": confidence,
                        "product_name": "",
                        "date_signal": "",
                    },
                ):
                    result.telegram = True
            except Exception as exc:
                logger.error("Telegram dashboard brief routing error: %s", exc, exc_info=True)
                result.skipped.append("telegram")

        if self._should_email(user, None, result):
            try:
                email_body = body
                dashboard_url = _dashboard_url(dashboard_path)
                if dashboard_url and dashboard_url not in email_body:
                    email_body = f"{email_body}\n\nOpen dashboard: {dashboard_url}"
                _send_email_message(user, title[:255], email_body, html)
                result.email = True
            except Exception as exc:
                logger.error("Email dashboard brief routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        return result

    def route_product_update_reminder(self, user, products, cadence_hours: int = 24) -> RoutingResult:
        """
        Send a grouped reminder asking the user to refresh stale product counts.
        The reminder respects the user's preferred channel and is throttled so it
        can be scheduled frequently without causing noise.
        """
        from apps.notifications.dispatch import (
            _build_product_update_body,
            _build_product_update_email_html,
            _build_product_update_title,
            _send_email_message,
        )
        from apps.notifications.models import Notification, NotificationThrottle
        from apps.notifications.telegram import send_product_update_reminder

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

        preferred = getattr(user, "preferred_channel", "email")

        if preferred == "telegram" and self._should_telegram(user, None):
            try:
                profile = user.telegram_profile
                if send_product_update_reminder(profile.chat_id, products):
                    result.telegram = True
            except Exception as exc:
                logger.error("Telegram reminder routing error: %s", exc, exc_info=True)
                result.skipped.append("telegram")
        if self._should_email(user, None, result):
            try:
                if _send_email_message(user, title[:255], body, html):
                    result.email = True
            except Exception as exc:
                logger.error("Email reminder routing error: %s", exc, exc_info=True)
                result.skipped.append("email")

        if result.any_delivered:
            NotificationThrottle.record(user, None, REMINDER_THROTTLE_CHANNEL)

        return result

    def _should_telegram(self, user, decision) -> bool:
        """Send via Telegram if user has linked their account and it's enabled."""
        preferred = getattr(user, "preferred_channel", "email")
        if preferred != "telegram":
            return False
        if not getattr(user, "telegram_enabled", False):
            return False
        try:
            profile = user.telegram_profile
            return profile.is_active
        except Exception:
            return False

    def _should_email(self, user, decision, result: RoutingResult) -> bool:
        """
        Send email if the user has email delivery enabled and either:
          - email is the preferred channel
          - telegram was preferred but is not currently linked/delivered
          - Pro routing needs a fallback after no premium channel delivered
        """
        if not getattr(user, "email", "") or not getattr(user, "email_notifications_enabled", True):
            return False
        preferred = getattr(user, "preferred_channel", "email")
        if preferred == "whatsapp":
            preferred = "email"
        if not user.is_pro:
            if preferred == "email":
                return True
            return preferred == "telegram" and not result.telegram
        else:
            if preferred == "email":
                return True
            return not result.telegram
