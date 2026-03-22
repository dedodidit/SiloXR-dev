# backend/apps/engine/gating.py

"""
Intelligence Gating Layer.

Controls how much of SiloXR's intelligence is exposed to any given user.
This is the anti-extraction layer — it prevents competitors from easily
reverse-engineering the system's logic by copying outputs.

Intelligence level = f(data_maturity, engagement, account_age)

Level 1 (0–30):   Surface — basic signals only
Level 2 (30–60):  Pattern — trend-aware signals
Level 3 (60–80):  Financial — demand-adjusted signals
Level 4 (80–100): Advanced — full signal fusion output

Reasoning abstraction rules:
  Level 1: "Stock may need attention."
  Level 2: "Sales patterns suggest monitoring this product."
  Level 3: "Consumption trends indicate a reorder in ~N days."
  Level 4: Full reasoning with confidence breakdown.

NEVER expose:
  - Raw burn rate values
  - SRS / IRS scores
  - Internal formula outputs
  - Signal conflict ratios
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Intelligence levels ────────────────────────────────────────────────────────

LEVEL_SURFACE   = 1
LEVEL_PATTERN   = 2
LEVEL_FINANCIAL = 3
LEVEL_ADVANCED  = 4


@dataclass(frozen=True)
class GatingContext:
    intelligence_level: int    # 1–4
    reasoning_depth:    str    # "surface" | "pattern" | "financial" | "advanced"
    max_products:       int    # how many products get full analysis
    show_confidence:    bool   # whether to show exact confidence %
    show_forecast:      bool   # whether to expose the forecast strip
    show_decisions:     bool   # whether to expose decision cards


class IntelligenceGate:
    """
    Determines the intelligence level for a user+product combination
    and applies appropriate reasoning abstraction.
    """

    def compute_level(self, user, product) -> int:
        """
        level = f(data_maturity * 0.5 + engagement * 0.3 + account_age * 0.2)
        Clamped to 1–4.
        """
        maturity_score = product.data_maturity_score

        # Engagement score from behavioral model
        engagement = self._get_engagement(user)

        # Account age contribution (days since registration, capped at 90)
        from django.utils import timezone
        if hasattr(user, "date_joined") and user.date_joined:
            age_days   = (timezone.now() - user.date_joined).days
            age_score  = min(100.0, age_days / 90.0 * 100)
        else:
            age_score  = 0.0

        raw = (
            maturity_score * 0.50 +
            engagement     * 0.30 +
            age_score      * 0.20
        )

        if raw < 25:  return LEVEL_SURFACE
        if raw < 55:  return LEVEL_PATTERN
        if raw < 80:  return LEVEL_FINANCIAL
        return LEVEL_ADVANCED

    def build_context(self, user, product) -> GatingContext:
        """Build a GatingContext for this user+product pair."""
        level    = self.compute_level(user, product)
        depth_map = {
            LEVEL_SURFACE:   "surface",
            LEVEL_PATTERN:   "pattern",
            LEVEL_FINANCIAL: "financial",
            LEVEL_ADVANCED:  "advanced",
        }

        return GatingContext(
            intelligence_level = level,
            reasoning_depth    = depth_map[level],
            max_products       = 999,
            show_confidence    = level >= LEVEL_PATTERN,
            show_forecast      = level >= LEVEL_PATTERN,
            show_decisions     = True,
        )

    def abstract_reasoning(self, full_reasoning: str, depth: str) -> str:
        """
        Strips internal detail from reasoning for lower intelligence levels.
        Returns a softened, abstracted version appropriate for the depth level.

        NEVER exposes: raw numbers, formula outputs, SRS/IRS scores.
        """
        if depth == "advanced":
            return full_reasoning

        if depth == "financial":
            # Remove specific numbers but keep direction
            import re
            # Replace specific day counts with approximate ranges
            result = re.sub(r"~(\d+) days", lambda m: self._approx_days(int(m.group(1))), full_reasoning)
            result = re.sub(r"\d+\.\d+ units", "current levels", result)
            return result

        if depth == "pattern":
            # Keep only the first sentence (the action) + confidence
            sentences = full_reasoning.split(".")
            first     = sentences[0].strip() if sentences else full_reasoning
            # Extract and reattach confidence if present
            import re
            conf_match = re.search(r"Confidence: (\d+)%", full_reasoning)
            if conf_match:
                return f"{first}. Confidence: {conf_match.group(1)}%."
            return f"{first}."

        # Surface — completely generic
        return "This product may need your attention soon."

    def _approx_days(self, days: int) -> str:
        if days <= 3:   return "a few days"
        if days <= 7:   return "about a week"
        if days <= 14:  return "1–2 weeks"
        if days <= 30:  return "this month"
        return "the coming weeks"

    def _get_engagement(self, user) -> float:
        """Fetch engagement score from behavioral model."""
        try:
            from apps.engine.behavioral import BehavioralEngine
            return BehavioralEngine().get_engagement_score(user)
        except Exception:
            return 25.0   # default mid-point


# ── Free tier product coverage ─────────────────────────────────────────────────

def apply_coverage_limit(products: list, user, gate: IntelligenceGate) -> tuple[list, int]:
    """
    Returns (visible_products, total_count).
    All users see all products.
    Commercial control is handled through refresh frequency, not feature coverage.
    """
    total = len(products)
    return products, total
