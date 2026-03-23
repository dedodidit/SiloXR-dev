# backend/apps/notifications/telegram.py

"""
Telegram notification channel.

Uses the Telegram Bot API directly via requests — no heavy library needed.
The bot must be set up at @BotFather first.

Linking flow:
  1. User clicks "Connect Telegram" in profile
  2. They open the bot and send /start {link_token}
  3. Bot webhook calls /api/telegram/webhook/
  4. We match token to user, create TelegramProfile

Interactive feedback:
  Insights sent via Telegram include inline keyboard with
  👍 / 👎 buttons. Callback data: feedback:{decision_id}:{rating}
"""

import hashlib
import hmac
import json
import logging
from datetime import timedelta

try:
    import requests
except ImportError:  # pragma: no cover - environment-dependent fallback
    requests = None
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Bot API base URL
BOT_API = "https://api.telegram.org/bot{token}/{method}"


def _api(method: str, **kwargs) -> dict | None:
    """Call the Telegram Bot API."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram call")
        return None
    if requests is None:
        logger.warning("requests is not installed — skipping Telegram call")
        return None
    try:
        url  = BOT_API.format(token=token, method=method)
        resp = requests.post(url, json=kwargs, timeout=8)
        data = resp.json()
        if not data.get("ok"):
            logger.error("Telegram API error for %s: %s", method, data.get("description"))
        return data
    except Exception as exc:
        logger.error("Telegram API exception for %s: %s", method, exc, exc_info=True)
        return None


def send_insight(chat_id: int, insight: dict, decision_id: str = "") -> bool:
    """
    Send a structured insight message with inline feedback keyboard.

    insight dict keys:
      title, reasoning, confidence, action_type, date_signal, product_name
    """
    conf      = insight.get("confidence", 0.5)
    conf_pct  = int(conf * 100)
    title     = insight.get("title", insight.get("observation", ""))
    reasoning = insight.get("reasoning", "")
    date_sig  = insight.get("date_signal", "")
    product   = insight.get("product_name", "")

    # Confidence-adaptive language
    if conf >= 0.70:
        hedge = "Expected"
        conf_label = "\u2705"   # ✅
    elif conf >= 0.45:
        hedge = "Likely"
        conf_label = "\u26A0\uFE0F"   # ⚠️
    else:
        hedge = "Possibly"
        conf_label = "\u2139\uFE0F"   # ℹ️

    date_part = f" ({date_sig})" if date_sig else ""

    text = (
        f"{conf_label} *{hedge}: {title}{date_part}*\n\n"
        f"_{reasoning}_\n\n"
        f"Confidence: {conf_pct}%"
    )

    keyboard = None
    if decision_id:
        keyboard = {
            "inline_keyboard": [[
                {"text": "\U0001F44D Helpful",   "callback_data": f"feedback:{decision_id}:helpful"},
                {"text": "\U0001F44E Not useful", "callback_data": f"feedback:{decision_id}:unhelpful"},
            ]]
        }

    result = _api(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return bool(result and result.get("ok"))


def send_decision_alert(chat_id: int, decision, product) -> bool:
    """
    Send a full decision alert (ALERT_CRITICAL / ALERT_LOW / REORDER).
    Used for high-urgency notifications.
    """
    from apps.engine.gating import IntelligenceGate
    from apps.engine.decision import ReasoningComposer

    conf     = decision.confidence_score
    conf_pct = int(conf * 100)
    action   = decision.action.replace("_", " ").title()

    sev_emoji = {
        "critical": "\U0001F6A8",   # 🚨
        "warning":  "\u26A0\uFE0F", # ⚠️
        "info":     "\U0001F4CB",   # 📋
        "ok":       "\u2705",       # ✅
    }.get(decision.severity, "\U0001F4CB")

    text = (
        f"{sev_emoji} *{action}: {product.name}*\n\n"
        f"{decision.reasoning}\n\n"
        f"*Confidence:* {conf_pct}%\n"
        f"*Stock:* ~{product.estimated_quantity:.0f} {product.unit}"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "\U0001F44D Helpful",    "callback_data": f"feedback:{decision.id}:helpful"},
            {"text": "\U0001F44E Not useful",  "callback_data": f"feedback:{decision.id}:unhelpful"},
            {"text": "\U0001F4CA Dashboard",   "callback_data": "open_dashboard"},
        ]]
    }

    result = _api(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return bool(result and result.get("ok"))


def send_product_update_reminder(chat_id: int, products) -> bool:
    """
    Send a grouped reminder asking the user to refresh stale product counts.
    """
    if not products:
        return False

    lines = [
        "\U0001F4E6 *Stock update needed*",
        "",
        "A few products need a fresh stock count so SiloXR can keep guidance accurate:",
        "",
    ]

    now = timezone.now()
    for product in products:
        if product.last_verified_at:
            stale_days = max(1, (now - product.last_verified_at).days)
            status = f"{stale_days} day{'s' if stale_days != 1 else ''} since last count"
        else:
            status = "no stock count logged yet"
        lines.append(f"• *{product.name}* ({product.sku}) — {status}")

    frontend = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    text = "\n".join(lines)
    keyboard = {
        "inline_keyboard": [[
            {"text": "\U0001F4CA Open dashboard", "callback_data": "open_dashboard"},
        ]]
    }

    if frontend:
        text = f"{text}\n\nOpen dashboard: {frontend}/products"

    result = _api(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return bool(result and result.get("ok"))


def generate_link_token(user) -> str:
    """
    Generate a short-lived token the user sends to the bot to link their account.
    Token stored in cache for 30 minutes.
    """
    token = hashlib.sha256(
        f"{user.id}{timezone.now().timestamp()}".encode()
    ).hexdigest()[:12].upper()

    cache.set(f"telegram_link:{token}", str(user.id), timeout=1800)
    return token


def process_webhook(update: dict) -> None:
    """
    Process an incoming Telegram update.
    Handles:
      - /start {token}  → link account
      - callback_query  → process feedback
    """
    # Handle callback queries (button presses)
    if "callback_query" in update:
        _handle_callback(update["callback_query"])
        return

    message = update.get("message", {})
    text    = message.get("text", "").strip()
    chat_id = message.get("chat", {}).get("id")

    if not chat_id:
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            _link_account(chat_id, parts[1].strip(), message)
        else:
            _api("sendMessage", chat_id=chat_id,
                 text="Welcome to SiloXR! To link your account, go to your profile and click 'Connect Telegram'.")


def _link_account(chat_id: int, token: str, message: dict) -> None:
    from django.contrib.auth import get_user_model
    from apps.notifications.models import TelegramProfile

    user_id = cache.get(f"telegram_link:{token}")
    if not user_id:
        _api("sendMessage", chat_id=chat_id,
             text="\u274C Token expired or invalid. Please generate a new link in your SiloXR profile.")
        return

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    TelegramProfile.objects.update_or_create(
        user=user,
        defaults={
            "chat_id":  chat_id,
            "username": message.get("from", {}).get("username", ""),
            "is_active": True,
        },
    )
    user.telegram_enabled = True
    user.save(update_fields=["telegram_enabled"])
    cache.delete(f"telegram_link:{token}")

    _api("sendMessage", chat_id=chat_id,
         text=f"\u2705 Account linked! You'll now receive SiloXR insights for *{user.username}* here.",
         parse_mode="Markdown")
    logger.info("Telegram linked for user %s → chat_id %s", user.username, chat_id)


def _handle_callback(callback: dict) -> None:
    """Process inline keyboard button presses."""
    data    = callback.get("data", "")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    query_id = callback.get("id")

    # Acknowledge the callback so the loading indicator stops
    if query_id:
        _api("answerCallbackQuery", callback_query_id=query_id)

    if data.startswith("feedback:"):
        parts = data.split(":")
        if len(parts) == 3:
            decision_id = parts[1]
            rating      = parts[2]  # helpful / unhelpful
            _record_telegram_feedback(decision_id, rating, callback)

    elif data == "open_dashboard":
        frontend = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
        _api("sendMessage", chat_id=chat_id,
             text=f"\U0001F4CA Open your dashboard: {frontend}")


def _record_telegram_feedback(decision_id: str, rating: str, callback: dict) -> None:
    """Store feedback from Telegram interaction."""
    from apps.notifications.models import TelegramProfile
    from apps.inventory.models import InsightFeedback, DecisionLog

    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    try:
        profile  = TelegramProfile.objects.select_related("user").get(chat_id=chat_id)
        decision = DecisionLog.objects.get(id=decision_id)
        InsightFeedback.objects.create(
            user         = profile.user,
            decision     = decision,
            product      = decision.product,
            was_helpful  = (rating == "helpful"),
            was_accurate = None,
            comment      = "via_telegram",
        )
        logger.info("Telegram feedback recorded: %s → %s", decision_id, rating)
    except Exception as exc:
        logger.error("Telegram feedback error: %s", exc)
