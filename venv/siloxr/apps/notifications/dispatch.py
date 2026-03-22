# backend/apps/notifications/dispatch.py

import logging

from django.conf import settings
from django.core.mail import send_mail

from apps.inventory.models import DecisionLog
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def dispatch_decision_notification(decision: DecisionLog) -> None:
    """
    Route a decision notification through all appropriate channels.
    """
    from apps.notifications.router import NotificationRouter

    NotificationRouter().route_decision(decision, decision.product)


def dispatch_insight_notifications(product, insights) -> int:
    """
    Create lightweight in-app notifications for freshly generated insights.
    This keeps the signal pipeline operational without introducing a second
    notification stack.
    """
    created = 0
    user = getattr(product, "owner", None)
    if user is None:
        return created

    for insight in insights or []:
        title = getattr(insight, "title", "") or f"Insight: {product.name}"
        body = getattr(insight, "message", "") or getattr(insight, "reasoning", "") or ""
        confidence = float(getattr(insight, "confidence", 0.5) or 0.5)
        if not body:
            continue
        Notification.objects.create(
            user=user,
            channel=Notification.CHANNEL_IN_APP,
            title=title[:255],
            body=body,
            confidence=confidence,
        )
        created += 1
    return created


def _build_title(decision: DecisionLog) -> str:
    prefix = {
        DecisionLog.ALERT_CRITICAL: "Urgent",
        DecisionLog.ALERT_LOW: "Heads up",
        DecisionLog.REORDER: "Suggestion",
        DecisionLog.CHECK_STOCK: "Action needed",
        DecisionLog.MONITOR: "FYI",
        DecisionLog.HOLD: "All clear",
    }.get(decision.action, "Update")
    return f"{prefix}: {decision.product.name}"


def _build_body(decision: DecisionLog) -> str:
    confidence = int((decision.confidence_score or 0) * 100)
    return f"{decision.reasoning}\n\nConfidence: {confidence}%"


def _build_email_html(decision: DecisionLog, title: str, body: str) -> str:
    confidence = int((decision.confidence_score or 0) * 100)
    product = decision.product
    severity = getattr(decision, "severity", "info").title()

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #141412;">
        <h2 style="margin-bottom: 8px;">{title}</h2>
        <p style="margin: 0 0 12px;"><strong>Severity:</strong> {severity}</p>
        <p style="margin: 0 0 12px;"><strong>Recommendation:</strong> {_recommendation(decision)}</p>
        <p style="margin: 0 0 12px; white-space: pre-line;">{body}</p>
        <p style="margin: 0; color: #6B6A66;">
          Product: {product.name} ({product.sku})<br />
          Estimated stock: {round(product.estimated_quantity)} {product.unit}<br />
          Confidence: {confidence}%
        </p>
      </body>
    </html>
    """


def _send_email(user, decision: DecisionLog, title: str, body: str) -> bool:
    if not getattr(user, "email", ""):
        return False

    send_mail(
        subject=title,
        message=f"{_recommendation(decision)}\n\n{body}",
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@siloxr.local"),
        recipient_list=[user.email],
        html_message=_build_email_html(decision, title, body),
        fail_silently=True,
    )
    return True


def _send_whatsapp(user, decision: DecisionLog, title: str, body: str) -> bool:
    if not getattr(user, "phone_number", ""):
        return False

    logger.info(
        "WhatsApp queued for %s (%s): %s | %s",
        user.username,
        user.phone_number,
        title,
        _recommendation(decision),
    )
    return True


def _recommendation(decision: DecisionLog) -> str:
    if decision.action == DecisionLog.ALERT_CRITICAL:
        return "Reorder immediately."
    if decision.action == DecisionLog.ALERT_LOW:
        return "Prepare a replenishment soon."
    if decision.action == DecisionLog.REORDER:
        return "Place a reorder."
    if decision.action == DecisionLog.CHECK_STOCK:
        return "Verify the shelf count."
    return "Keep monitoring the product."
