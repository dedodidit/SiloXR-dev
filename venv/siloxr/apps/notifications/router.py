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

# Minimum confidence for WhatsApp delivery
WHATSAPP_CONF_FLOOR = 0.70

# WhatsApp throttle settings
WHATSAPP_COOLDOWN_HOURS = 6
WHATSAPP_MAX_PER_DAY    = 1


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
        from apps.notifications.dispatch import (
            _build_title, _build_body, _build_email_html,
            _send_email, _send_whatsapp,
        )
        from apps.notifications.models import Notification, NotificationThrottle

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

        # ── 3. WhatsApp (pro only, confidence gated, throttled) ──────────
        if self._should_whatsapp(user, decision, product):
            try:
                _send_whatsapp(user, decision, title, body)
                NotificationThrottle.record(user, product, "whatsapp")
                result.whatsapp = True
                logger.info("WhatsApp delivered for %s → %s", user.username, decision.action)
            except Exception as exc:
                logger.error("WhatsApp routing error: %s", exc, exc_info=True)
                result.skipped.append("whatsapp")

        # ── 4. Email (free fallback or pro supplement) ───────────────────
        if self._should_email(user, decision, result):
            try:
                html = _build_email_html(decision, title, body)
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

    def _should_telegram(self, user, decision) -> bool:
        """Send via Telegram if user has linked their account and it's enabled."""
        if not getattr(user, "telegram_enabled", False):
            return False
        try:
            profile = user.telegram_profile
            return profile.is_active
        except Exception:
            return False

    def _should_whatsapp(self, user, decision, product) -> bool:
        """WhatsApp: Pro only, confidence gated, severity gated, throttled."""
        if not user.is_pro:
            return False
        if not getattr(user, "phone_number", "") or not getattr(user, "whatsapp_enabled", False):
            return False
        if decision.confidence_score < WHATSAPP_CONF_FLOOR:
            return False
        if decision.severity not in ("critical", "warning"):
            return False
        # "Critical only" mode
        if getattr(user, "whatsapp_critical_only", False):
            if decision.action != "ALERT_CRITICAL":
                return False
        # Throttle check
        from apps.notifications.models import NotificationThrottle
        throttle = NotificationThrottle.objects.filter(
            user=user, product=product, channel="whatsapp"
        ).first()
        if throttle and throttle.is_throttled(WHATSAPP_COOLDOWN_HOURS, WHATSAPP_MAX_PER_DAY):
            logger.debug("WhatsApp throttled for %s/%s", user.username, product.sku)
            return False
        return True

    def _should_email(self, user, decision, result: RoutingResult) -> bool:
        """
        Send email if:
          - Free user AND preferred_channel = email AND no telegram delivered
          - Or Pro user AND email_notifications_enabled AND no other channel delivered
        """
        if not getattr(user, "email", "") or not getattr(user, "email_notifications_enabled", True):
            return False
        preferred = getattr(user, "preferred_channel", "email")
        if not user.is_pro:
            # Free: only email if telegram not delivered and preference is email
            return preferred == "email" and not result.telegram
        else:
            # Pro: email as fallback if nothing else delivered
            return not result.telegram and not result.whatsapp