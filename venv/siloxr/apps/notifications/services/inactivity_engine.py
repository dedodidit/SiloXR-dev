from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.inventory.models import InventoryEvent


@dataclass
class InactivityRiskResult:
    user_id: str
    message: str
    notification_type: str
    severity: str
    should_notify: bool
    reference_id: str
    confidence: float
    days_inactive: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _latest_activity_at(user):
    latest_event = (
        InventoryEvent.objects.filter(product__owner=user)
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )
    login_at = getattr(user, "last_login", None)
    if latest_event and login_at:
        return latest_event if latest_event >= login_at else login_at
    return latest_event or login_at or getattr(user, "date_joined", None)


def evaluate_user_inactivity(user) -> InactivityRiskResult:
    """
    Evaluate user activity based on the latest inventory event,
    falling back to the last login timestamp.
    """
    now = timezone.now()
    last_activity_at = _latest_activity_at(user)
    if last_activity_at is None:
        last_activity_at = getattr(user, "date_joined", now)

    days_inactive = max(0.0, (now - last_activity_at).total_seconds() / 86400.0)
    if days_inactive < 1.0:
        return InactivityRiskResult(
            user_id=str(user.id),
            message="Activity looks current.",
            notification_type="",
            severity="low",
            should_notify=False,
            reference_id=f"user:{user.id}",
            confidence=0.35,
            days_inactive=days_inactive,
            metadata={"last_activity_at": last_activity_at.isoformat()},
        )

    if days_inactive < 2.0:
        severity = "low"
        message = "You have not logged activity recently, so some demand changes may be easier to miss."
        confidence = 0.55
    elif days_inactive < 5.0:
        severity = "medium"
        message = "Recent activity has slowed, so some stock shifts may be going unnoticed."
        confidence = 0.7
    else:
        severity = "high"
        message = "No recent updates have been recorded, so sales changes or stock gaps may be slipping through."
        confidence = 0.85

    return InactivityRiskResult(
        user_id=str(user.id),
        message=message,
        notification_type="inactivity_risk",
        severity=severity,
        should_notify=True,
        reference_id=f"user:{user.id}",
        confidence=confidence,
        days_inactive=days_inactive,
        metadata={
            "last_activity_at": last_activity_at.isoformat(),
            "login_at": getattr(getattr(user, "last_login", None), "isoformat", lambda: None)(),
        },
    )
