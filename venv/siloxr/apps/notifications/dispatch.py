# backend/apps/notifications/dispatch.py

import logging
from html import escape
import hashlib
import json

from django.conf import settings
from django.core.cache import cache
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


def dispatch_dashboard_insights(user, contextual_insights, managerial_signals, cadence_hours: int = 12) -> int:
    """
    Route dashboard-generated insights through the notification system while
    debouncing repeated sends from frequent dashboard refreshes.
    """
    normalized = []

    for item in contextual_insights or []:
        title = item.get("title") or item.get("observation") or "Dashboard insight"
        body = item.get("summary") or item.get("recommendation") or item.get("message") or ""
        if not body:
            continue
        normalized.append(
            {
                "title": title,
                "body": body,
                "confidence": float(item.get("confidence", 0.55) or 0.55),
                "dashboard_path": "/dashboard",
            }
        )

    for item in managerial_signals or []:
        title = item.get("title") or "Managerial signal"
        summary = item.get("summary") or ""
        recommendation = item.get("recommendation") or ""
        value = item.get("value")
        body_parts = [summary]
        if value not in (None, ""):
            body_parts.append(f"Current value: {value}")
        if recommendation:
            body_parts.append(recommendation)
        body = "\n\n".join(part for part in body_parts if part)
        if not body:
            continue
        target = item.get("target") or "dashboard"
        normalized.append(
            {
                "title": title,
                "body": body,
                "confidence": 0.6 if item.get("tone") in {"critical", "warning"} else 0.5,
                "dashboard_path": f"/dashboard#{target}",
            }
        )

    if not normalized:
        return 0

    fingerprint = hashlib.sha256(
        json.dumps(normalized[:3], sort_keys=True).encode("utf-8")
    ).hexdigest()
    cache_key = f"dashboard_insights_notified:{user.id}:{fingerprint}"
    if cache.get(cache_key):
        return 0

    from apps.notifications.router import NotificationRouter

    router = NotificationRouter()
    sent = 0
    for insight in normalized[:3]:
        sent += 1 if router.route_dashboard_insight(user, insight).in_app else 0

    if sent:
        cache.set(cache_key, True, timeout=max(3600, cadence_hours * 3600))
    return sent


def dispatch_dashboard_brief(user, summary_data, brief_type: str) -> bool:
    """
    Send a grouped dashboard brief for start/end of business.
    """
    from apps.notifications.router import NotificationRouter

    if not summary_data:
        return False

    title = _build_dashboard_brief_title(brief_type)
    body = _build_dashboard_brief_body(summary_data, brief_type)
    html = _build_dashboard_brief_email_html(user, summary_data, title, brief_type)

    result = NotificationRouter().route_dashboard_brief(
        user,
        {
            "title": title,
            "body": body,
            "html": html,
            "confidence": 0.62,
            "dashboard_path": "/dashboard",
        },
    )
    return result.any_delivered


def notification_channel_status(user) -> dict:
    preferred = getattr(user, "preferred_channel", "email")
    email_address = getattr(user, "email", "") or ""
    telegram_profile = getattr(user, "telegram_profile", None)
    telegram_linked = bool(telegram_profile and getattr(telegram_profile, "is_active", False))
    email_configured = _email_configured()
    email_enabled = bool(getattr(user, "email_notifications_enabled", True) and email_address)
    email_ready = email_enabled and email_configured
    telegram_enabled = bool(getattr(user, "telegram_enabled", False))
    telegram_ready = telegram_enabled and telegram_linked

    def _last_sent(channel: str) -> str | None:
        sent_at = (
            Notification.objects
            .filter(user=user, channel=channel)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        return sent_at.isoformat() if sent_at else None

    issues = []
    if preferred == "email" and not email_ready:
        if not email_enabled:
            issues.append("Email delivery is disabled on your profile.")
        elif not email_configured:
            issues.append("Email delivery is not configured on the server.")
    if preferred == "telegram" and not telegram_ready:
        issues.append("Telegram is selected but not fully linked yet.")
    if not email_ready and not telegram_ready:
        issues.append("Only in-app notifications are currently guaranteed.")

    recommended_channel = "email" if email_ready else "telegram" if telegram_ready else "in_app"

    return {
        "preferred_channel": preferred,
        "recommended_channel": recommended_channel,
        "issues": issues,
        "email": {
            "enabled": email_enabled,
            "configured": email_configured,
            "ready": email_ready,
            "address": email_address,
            "last_sent_at": _last_sent(Notification.CHANNEL_EMAIL),
        },
        "telegram": {
            "enabled": telegram_enabled,
            "linked": telegram_linked,
            "ready": telegram_ready,
            "username": getattr(telegram_profile, "username", "") if telegram_profile else "",
            "last_sent_at": _last_sent(Notification.CHANNEL_TELEGRAM),
        },
        "whatsapp": {
            "ready": False,
            "enabled": False,
            "issue": "WhatsApp delivery is temporarily disabled.",
        },
    }


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
    dashboard_url = _dashboard_url("/dashboard")
    products_url = _dashboard_url("/products")
    ctas = []
    if dashboard_url:
        ctas.append(_build_cta_html("Open dashboard", dashboard_url))
    if products_url:
        ctas.append(_build_cta_html("Review products", products_url))

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
        {''.join(ctas)}
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


def _build_insight_email_html(user, title: str, body: str, dashboard_path: str = "/dashboard") -> str:
    dashboard_url = _dashboard_url(dashboard_path)
    cta = _build_cta_html("Open dashboard", dashboard_url) if dashboard_url else ""
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #141412;">
        <h2 style="margin-bottom: 8px;">{escape(title)}</h2>
        <p style="margin: 0 0 12px;">Hi {escape(user.first_name or user.username or 'there')},</p>
        <p style="margin: 0 0 12px; white-space: pre-line;">{escape(body)}</p>
        {cta}
      </body>
    </html>
    """


def _build_dashboard_brief_title(brief_type: str) -> str:
    if brief_type == "opening":
        return "Opening brief: SiloXR dashboard"
    if brief_type == "closing":
        return "Closing brief: SiloXR dashboard"
    return "Business brief: SiloXR dashboard"


def _build_dashboard_brief_body(summary_data, brief_type: str) -> str:
    lines = []
    if brief_type == "opening":
        lines.append("Here is your start-of-business dashboard brief.")
    elif brief_type == "closing":
        lines.append("Here is your close-of-business dashboard brief.")
    else:
        lines.append("Here is your dashboard brief.")

    managerial = (summary_data or {}).get("managerial_brief", {}) or {}
    if managerial.get("headline"):
        lines.extend(["", managerial["headline"]])
    if managerial.get("subtext"):
        lines.append(managerial["subtext"])

    contextual = list((summary_data or {}).get("contextual_insights", []) or [])[:3]
    if contextual:
        lines.extend(["", "Top dashboard insights:"])
        for item in contextual:
            title = item.get("title") or item.get("observation") or "Insight"
            summary = item.get("summary") or item.get("recommendation") or ""
            lines.append(f"- {title}: {summary}")

    signals = list((summary_data or {}).get("managerial_signals", []) or [])[:2]
    if signals:
        lines.extend(["", "Key management signals:"])
        for item in signals:
            label = item.get("title") or "Signal"
            value = item.get("value")
            summary = item.get("summary") or ""
            prefix = f"{label} ({value})" if value not in (None, "") else label
            lines.append(f"- {prefix}: {summary}")

    dashboard_url = _dashboard_url("/dashboard")
    if dashboard_url:
        lines.extend(["", f"Open dashboard: {dashboard_url}"])

    return "\n".join(lines)


def _build_dashboard_brief_email_html(user, summary_data, title: str, brief_type: str) -> str:
    contextual = list((summary_data or {}).get("contextual_insights", []) or [])[:3]
    signals = list((summary_data or {}).get("managerial_signals", []) or [])[:2]
    managerial = (summary_data or {}).get("managerial_brief", {}) or {}

    intro = "start-of-business" if brief_type == "opening" else "close-of-business" if brief_type == "closing" else "business"
    contextual_items = "".join(
        f"<li><strong>{escape(item.get('title') or item.get('observation') or 'Insight')}</strong>"
        f" — {escape(item.get('summary') or item.get('recommendation') or '')}</li>"
        for item in contextual
    )
    signal_items = ""
    for item in signals:
        label = escape(item.get("title") or "Signal")
        value = item.get("value")
        value_part = f" ({escape(str(value))})" if value not in (None, "") else ""
        summary = escape(item.get("summary") or "")
        signal_items += f"<li><strong>{label}</strong>{value_part} — {summary}</li>"

    dashboard_url = _dashboard_url("/dashboard")
    products_url = _dashboard_url("/products")
    ctas = ""
    if dashboard_url:
        ctas += _build_cta_html("Open dashboard", dashboard_url)
    if products_url:
        ctas += _build_cta_html("Review products", products_url)

    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #141412;">
        <h2 style="margin-bottom: 8px;">{escape(title)}</h2>
        <p style="margin: 0 0 12px;">Hi {escape(user.first_name or user.username or 'there')}, here is your {escape(intro)} dashboard brief.</p>
        <p style="margin: 0 0 12px;"><strong>{escape(managerial.get('headline', 'Dashboard update'))}</strong></p>
        <p style="margin: 0 0 12px;">{escape(managerial.get('subtext', ''))}</p>
        <h3 style="margin: 16px 0 8px;">Top insights</h3>
        <ul style="margin: 0 0 16px 18px;">{contextual_items}</ul>
        <h3 style="margin: 16px 0 8px;">Management signals</h3>
        <ul style="margin: 0 0 16px 18px;">{signal_items}</ul>
        {ctas}
      </body>
    </html>
    """


def _send_email(user, decision: DecisionLog, title: str, body: str) -> bool:
    html = _build_email_html(decision, title, body)
    text_body = f"{_recommendation(decision)}\n\n{body}"
    dashboard_url = _dashboard_url("/dashboard")
    if dashboard_url:
        text_body = f"{text_body}\n\nOpen dashboard: {dashboard_url}"
    return _send_email_message(user, title, text_body, html)


def _send_email_message(user, title: str, body: str, html_message: str | None = None) -> bool:
    if not getattr(user, "email", ""):
        return False
    if not _email_configured():
        logger.error("Email skipped for %s because email delivery is not configured.", user.email)
        return False

    try:
        sent = send_mail(
            subject=title,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@siloxr.local"),
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("Email delivery failed for %s: %s", user.email, exc, exc_info=True)
        return False
    if sent <= 0:
        logger.error("Email delivery returned zero messages sent for %s.", user.email)
        return False
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


def _dashboard_url(path: str = "/dashboard") -> str:
    frontend = getattr(settings, "FRONTEND_BASE_URL", "").rstrip("/")
    if not frontend:
        return ""
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{frontend}{path}"


def _email_configured() -> bool:
    backend = str(getattr(settings, "EMAIL_BACKEND", "") or "")
    if backend.endswith(("console.EmailBackend", "locmem.EmailBackend", "filebased.EmailBackend")):
        return True
    required = [
        getattr(settings, "EMAIL_HOST", ""),
        getattr(settings, "EMAIL_PORT", ""),
        getattr(settings, "DEFAULT_FROM_EMAIL", ""),
    ]
    auth_required = [getattr(settings, "EMAIL_HOST_USER", ""), getattr(settings, "EMAIL_HOST_PASSWORD", "")]
    return all(required) and all(auth_required)


def record_channel_delivery(user, channel: str, title: str, body: str, confidence: float = 0.5, decision=None) -> None:
    Notification.objects.create(
        user=user,
        decision=decision,
        channel=channel,
        title=title[:255],
        body=body,
        confidence=confidence,
        is_read=True,
        read_at=timezone.now(),
    )


def _build_cta_html(label: str, url: str) -> str:
    if not url:
        return ""
    return (
        f'<p style="margin: 16px 0 0;">'
        f'<a href="{escape(url)}" '
        f'style="color: #0F766E; text-decoration: none; font-weight: 600;">'
        f"{escape(label)}</a></p>"
    )
