# backend/apps/engine/behavioral.py

"""
Behavioral Dependency Engine.

Tracks user engagement with SiloXR's intelligence outputs
and uses it to:
  1. Personalise intelligence level (via gating.py)
  2. Increase value gradually (reduce noise as trust builds)
  3. Build reliance through demonstrated accuracy

dependency_score = insights_viewed + nudges_answered + decisions_used

This score is NOT shown to users. It is used internally to:
  - Determine intelligence level
  - Adjust nudge frequency
  - Unlock deeper reasoning over time
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class EngagementSummary:
    insights_viewed:    int
    nudges_answered:    int
    decisions_used:     int
    dependency_score:   float
    engagement_score:   float    # 0–100, used by gating


class BehavioralEngine:
    """
    Computes and updates engagement metrics for a user.
    Lightweight — reads from existing DecisionLog + Notification models.
    """

    def get_engagement_score(self, user) -> float:
        """
        Returns a 0–100 engagement score for this user.
        Used by IntelligenceGate.compute_level().
        """
        summary = self.summarise(user)
        return summary.engagement_score

    def summarise(self, user) -> EngagementSummary:
        """Compute engagement summary from existing model data."""
        from apps.inventory.models import DecisionLog
        from apps.notifications.models import Notification

        # Decisions acknowledged = decisions used
        decisions_used = DecisionLog.objects.filter(
            product__owner=user,
            is_acknowledged=True,
        ).count()

        # Notifications read = insights viewed (proxy)
        insights_viewed = Notification.objects.filter(
            user=user, is_read=True
        ).count()

        # Nudges answered — tracked in nudge response log
        nudges_answered = self._count_nudge_responses(user)

        # Dependency score (raw)
        dependency_score = (
            insights_viewed * 1.0 +
            nudges_answered * 2.0 +  # weighted higher — active engagement
            decisions_used  * 1.5
        )

        # Normalise to 0–100 (cap at 200 total raw interactions)
        engagement_score = min(100.0, dependency_score / 200.0 * 100)

        return EngagementSummary(
            insights_viewed  = insights_viewed,
            nudges_answered  = nudges_answered,
            decisions_used   = decisions_used,
            dependency_score = round(dependency_score, 2),
            engagement_score = round(engagement_score, 2),
        )

    def record_interaction(self, user, interaction_type: str) -> None:
        """
        Record a user interaction for behavioral tracking.
        interaction_type: "insight_viewed" | "nudge_answered" | "decision_used"
        """
        # Lightweight: we derive from existing models rather than a separate table
        # This method is a hook for future explicit tracking
        logger.debug("Behavioral: %s by %s", interaction_type, user.username)

    def _count_nudge_responses(self, user) -> int:
        """Count nudge responses by checking STOCK_COUNT events with nudge notes."""
        from apps.inventory.models import InventoryEvent
        return InventoryEvent.objects.filter(
            product__owner=user,
            event_type=InventoryEvent.STOCK_COUNT,
            notes__icontains="nudge",
        ).count()