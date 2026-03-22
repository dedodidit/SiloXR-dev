# backend/apps/notifications/dispatch_gate.py
#
# Notification confidence gate (requirement 7).
#
# This is a NEW standalone module, not a modification of dispatch.py.
# dispatch.py imports and calls should_dispatch() before sending any
# push or WhatsApp notification.
#
# Why a separate file rather than editing dispatch.py?
#   - dispatch.py is wired into multiple call sites (signals, tasks, API).
#   - Adding inline conditionals throughout dispatch.py risks introducing
#     silent breakage across those call sites.
#   - A separate gate module is testable in isolation, importable anywhere,
#     and makes the policy explicit rather than scattered.
#
# Integration in dispatch.py
# ──────────────────────────
# At the top of dispatch.py, add:
#
#     from apps.notifications.dispatch_gate import should_dispatch
#
# Then wrap the WhatsApp and push send calls:
#
#     # WhatsApp
#     if should_dispatch("whatsapp", decision_log):
#         _send_whatsapp(user, decision_log, title, body)
#
#     # Push
#     if should_dispatch("push", decision_log):
#         _send_push(user, decision_log, title, body)
#
#     # In-app is always sent — never gated
#     Notification.objects.create(...)
#
# dispatch.py does not need any other changes.
# ─────────────────────────────────────────────────────────────────────────────

import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Gate thresholds ────────────────────────────────────────────────────────────

# Minimum confidence for any push/WhatsApp notification (requirement 7)
PUSH_CONFIDENCE_FLOOR     = 0.65

# WhatsApp is stricter than push — it is a personal channel with no mute option
WHATSAPP_CONFIDENCE_FLOOR = 0.65   # matches PUSH_CONFIDENCE_FLOOR per spec

# Actions that are always silent — never send WhatsApp or push for these
SILENT_ACTIONS = frozenset(["HOLD", "MONITOR"])

# Actions that require higher confidence for WhatsApp (critical-only mode)
# When whatsapp_critical_only is True on the user, only this set is sent
CRITICAL_ONLY_ACTIONS = frozenset(["ALERT_CRITICAL"])

# Trust-gate suppression note prefix — if DecisionLog.trust_gate_note starts
# with this, the action was downgraded and should not be pushed
GATED_NOTE_MARKER = ""   # any non-empty trust_gate_note means the action was gated


def should_dispatch(channel: str, decision_log) -> bool:
    """
    Returns True if a notification should be sent on the given channel
    for this DecisionLog.

    Parameters
    ──────────
    channel       "whatsapp" | "push" | "in_app" | "email"
    decision_log  A DecisionLog ORM instance. Must have:
                  .action, .confidence_score, .product.owner,
                  .trust_gate_note (new additive field, may be absent on
                  older records — handled gracefully).

    Rules
    ─────
    In-app:    always True — never gated. In-app notifications are the
               user's primary feed and must be comprehensive.

    Email:     always True — email is asynchronous and users can filter.
               Frequency is already controlled by the Notification model's
               daily-digest logic.

    Push:      gated by confidence >= PUSH_CONFIDENCE_FLOOR.
               Silent actions (HOLD, MONITOR) never trigger push.
               Actions that were downgraded by the trust gate are not pushed.

    WhatsApp:  same as push, plus: respects user's whatsapp_critical_only flag.
               If the flag is set, only ALERT_CRITICAL is dispatched.
    """

    # In-app and email are never gated by confidence
    if channel in ("in_app", "email"):
        return True

    action     = getattr(decision_log, "action", "")
    confidence = float(getattr(decision_log, "confidence_score", 0.0) or 0.0)

    # Silent actions never push or send WhatsApp
    if action in SILENT_ACTIONS:
        logger.debug(
            "Notification gated for %s: action %s is silent",
            getattr(decision_log.product, "sku", "?"), action,
        )
        return False

    # If the trust gate downgraded this action, do not notify via push/WhatsApp.
    # The user will see the decision in-app with the gate explanation.
    trust_note = getattr(decision_log, "trust_gate_note", "") or ""
    if trust_note:
        logger.debug(
            "Notification gated for %s: decision was downgraded by trust gate (%s → %s)",
            getattr(decision_log.product, "sku", "?"),
            getattr(decision_log, "original_action", "?"),
            action,
        )
        return False

    # Confidence floor — applies to both push and WhatsApp
    floor = (
        WHATSAPP_CONFIDENCE_FLOOR
        if channel == "whatsapp"
        else PUSH_CONFIDENCE_FLOOR
    )
    if confidence < floor:
        logger.debug(
            "Notification gated for %s: confidence %.2f < %.2f for channel %s",
            getattr(decision_log.product, "sku", "?"),
            confidence, floor, channel,
        )
        return False

    # WhatsApp: respect the user's critical-only preference
    if channel == "whatsapp":
        user = getattr(decision_log, "product", None)
        user = getattr(user, "owner", None) if user else None
        critical_only = getattr(user, "whatsapp_critical_only", False)
        if critical_only and action not in CRITICAL_ONLY_ACTIONS:
            logger.debug(
                "WhatsApp gated for %s: critical_only mode, action=%s",
                getattr(decision_log.product, "sku", "?"), action,
            )
            return False

    return True


def get_dispatch_reason(channel: str, decision_log) -> str:
    """
    Returns a human-readable explanation of why a notification was or
    was not sent on a given channel. Used for debugging and admin display.
    """
    if not should_dispatch(channel, decision_log):
        action     = getattr(decision_log, "action", "")
        confidence = float(getattr(decision_log, "confidence_score", 0.0) or 0.0)
        trust_note = getattr(decision_log, "trust_gate_note", "") or ""

        if action in SILENT_ACTIONS:
            return f"{channel}: suppressed — {action} is a silent action"
        if trust_note:
            orig = getattr(decision_log, "original_action", "?")
            return (
                f"{channel}: suppressed — decision was downgraded "
                f"from {orig} to {action} by the trust gate"
            )
        floor = (
            WHATSAPP_CONFIDENCE_FLOOR if channel == "whatsapp"
            else PUSH_CONFIDENCE_FLOOR
        )
        if confidence < floor:
            return (
                f"{channel}: suppressed — confidence {int(confidence * 100)}% "
                f"is below the {int(floor * 100)}% threshold"
            )
        if channel == "whatsapp":
            return f"{channel}: suppressed — critical-only mode is enabled"

    return f"{channel}: approved"