# backend/apps/notifications/dispatch.py

import logging
from html import escape

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

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
    Route insight notifications through the same channel logic as the rest of
    the system, while always keeping an in-app record.
    """
    created = 0
    user = getattr(product, "owner", None)
    if user is None:
        return created

    from apps.notifications.router import NotificationRouter
    router = NotificationRouter()

    for insight in insights or []:
        created += 1 if router.route_insight(user, product, insight).in_app else 0
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


def _build_product_update_title(products) -> str:
    count = len(products or [])
    if count <= 1:
        name = getattr(products[0], "name", "your product") if products else "your product"
        return f"Update needed: {name}"
    return f"Update needed: {count} products need a fresh stock count"


def _build_product_update_body(products) -> str:
    now = timezone.now()
    lines = [
        "Your inventory guidance is going stale for the products below.",
        "Log a fresh stock count so SiloXR can keep forecasts and alerts accurate.",
        "",
    ]
    for product in products or []:
        if product.last_verified_at:
            stale_days = max(1, (now - product.last_verified_at).days)
            status = f"last verified {stale_days} day{'s' if stale_days != 1 else ''} ago"
        else:
            status = "no stock count logged yet"
        lines.append(f"- {product.name} ({product.sku}): {status}")

    frontend = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    if frontend:
        lines.extend(["", f"Open dashboard: {frontend}/products"])

    return "\n".join(lines)


def _build_product_update_email_html(user, products, title: str, body: str) -> str:
    now = timezone.now()
    items = []
    for product in products or []:
        if product.last_verified_at:
            stale_days = max(1, (now - product.last_verified_at).days)
            status = f"Last verified {stale_days} day{'s' if stale_days != 1 else ''} ago"
        else:
            status = "No stock count logged yet"
        items.append(
            f"<li><strong>{escape(product.name)}</strong> ({escape(product.sku)})"
            f" — {escape(status)}</li>"
        )

    frontend = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    cta = ""
    if frontend:
        cta = (
            f'<p style="margin: 16px 0 0;">'
            f'<a href="{escape(frontend)}/products" '
            f'style="color: #0F766E; text-decoration: none; font-weight: 600;">'
            f"Open your products dashboard</a></p>"
        )

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #141412;">
        <h2 style="margin-bottom: 8px;">{escape(title)}</h2>
        <p style="margin: 0 0 12px;">Hi {escape(user.first_name or user.username or 'there')},</p>
        <p style="margin: 0 0 12px;">A few products need a fresh stock update so SiloXR can keep your guidance accurate.</p>
        <ul style="margin: 0 0 16px 18px;">
          {''.join(items)}
        </ul>
        <p style="margin: 0; white-space: pre-line; color: #6B6A66;">{escape(body)}</p>
        {cta}
      </body>
    </html>
    """


def _send_email(user, decision: DecisionLog, title: str, body: str) -> bool:
    html = _build_email_html(decision, title, body)
    return _send_email_message(user, title, f"{_recommendation(decision)}\n\n{body}", html)


def _send_email_message(user, title: str, body: str, html_message: str | None = None) -> bool:
    if not getattr(user, "email", ""):
        return False

    send_mail(
        subject=title,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@siloxr.local"),
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )
    return True


def _send_whatsapp(user, decision: DecisionLog, title: str, body: str) -> bool:
    return _send_whatsapp_message(user, title, f"{_recommendation(decision)}\n\n{body}")


def _send_whatsapp_message(user, title: str, body: str) -> bool:
    if not getattr(user, "phone_number", ""):
        return False

    logger.info(
        "WhatsApp queued for %s (%s): %s | %s",
        user.username,
        user.phone_number,
        title,
        body.splitlines()[0] if body else "",
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
