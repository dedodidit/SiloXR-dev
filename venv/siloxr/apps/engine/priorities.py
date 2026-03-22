# backend/apps/engine/priorities.py

from django.utils import timezone
from apps.inventory.models import DecisionLog


def get_top_priorities(user_id: str, limit: int = 3) -> list:
    """
    Return the most important active decisions for a user.

    Sort order: priority_score DESC → risk_score DESC → confidence DESC → oldest first.
    Only includes decisions that are still active (not expired, not acknowledged).
    This is the correct source for the DominantDecision hero card — not InsightEngine.
    """
    return list(
        DecisionLog.objects
        .filter(
            product__owner_id = user_id,
            expires_at__gt    = timezone.now(),
            is_acknowledged   = False,
            priority_score__gt = 0,
        )
        .exclude(action=DecisionLog.HOLD)
        .select_related("product", "product__owner")
        .order_by(
            "-priority_score",
            "-risk_score",
            "-confidence_score",
            "created_at",
        )[:limit]
    )
