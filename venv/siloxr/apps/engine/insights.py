# backend/apps/engine/insights.py

"""
Multi-Insight Engine.

Seven detectors, each producing StructuredInsight objects.
All detectors run through ReasoningEngine — no hardcoded strings.

Detectors:
  StockRiskDetector     — imminent stockout risk
  DemandShiftDetector   — trend direction change
  PatternDetector       — recurring weekly/monthly patterns
  ProfitRiskDetector    — overstock / capital inefficiency
  DataQualityDetector   — low confidence, needs more data
  AnomalyDetector       — unexpected consumption spike/drop
  OpportunityDetector   — undersupply vs rising demand
"""

import logging
import statistics
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.engine.reasoning import ReasoningEngine, StructuredInsight

logger = logging.getLogger(__name__)


class InsightEngine:
    """
    Orchestrates all detectors for a single product.
    Returns a list of StructuredInsight objects, deduplicated and ranked.
    """

    def __init__(self):
        self._reasoning = ReasoningEngine()
        self._detectors = [
            StockRiskDetector(self._reasoning),
            DemandShiftDetector(self._reasoning),
            PatternDetector(self._reasoning),
            ProfitRiskDetector(self._reasoning),
            DataQualityDetector(self._reasoning),
            AnomalyDetector(self._reasoning),
            OpportunityDetector(self._reasoning),
        ]

    def run(self, product, user=None) -> list[StructuredInsight]:
        """
        Run all detectors against a product.
        Returns insights sorted by severity then confidence.
        """
        business_type = self._get_business_type(user)
        insights      = []

        for detector in self._detectors:
            try:
                result = detector.detect(product, business_type)
                if result:
                    insights.append(result)
            except Exception as exc:
                logger.error(
                    "Detector %s failed for %s: %s",
                    detector.__class__.__name__, product.sku, exc, exc_info=True,
                )

        # Sort: critical first, then by confidence desc
        sev_order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
        insights.sort(key=lambda i: (sev_order.get(i.severity, 9), -i.confidence))

        return insights[:6]   # cap at 6 insights per product

    def run_for_user(self, user) -> list[StructuredInsight]:
        """
        Run insights across all active products for a user.
        Returns top insights across all products, deduplicated.
        """
        from apps.inventory.models import Product
        from apps.engine.gating import apply_coverage_limit, IntelligenceGate

        products = list(
            Product.objects.filter(owner=user, is_active=True)
            .prefetch_related("burn_rates", "events")
        )

        gate    = IntelligenceGate()
        visible, _ = apply_coverage_limit(products, user, gate)

        all_insights = []
        for product in visible:
            all_insights.extend(self.run(product, user))

        # Deduplicate by (product_id, detector)
        seen     = set()
        unique   = []
        for ins in all_insights:
            key = (ins.product_id, ins.detector)
            if key not in seen:
                seen.add(key)
                unique.append(ins)

        sev_order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
        unique.sort(key=lambda i: (sev_order.get(i.severity, 9), -i.confidence))
        return unique[:10]

    @staticmethod
    def _get_business_type(user) -> str:
        if user is None:
            return ""
        return getattr(user, "business_type", "") or ""
    
    # backend/apps/engine/insights.py
# ADD to InsightEngine class

    def get_dominant_insight(self, user) -> Optional[StructuredInsight]:
        """
        Returns the single most urgent insight across all visible products.
        This drives the DominantDecision hero card on the dashboard.
        """
        all_insights = self.run_for_user(user)
        if not all_insights:
            return None
        # Critical first, then by confidence
        critical = [i for i in all_insights if i.urgency_tier == "critical"]
        if critical:
            return max(critical, key=lambda i: i.confidence)
        warnings = [i for i in all_insights if i.urgency_tier == "warning"]
        if warnings:
            return max(warnings, key=lambda i: i.confidence)
        return all_insights[0]


# ── Base detector ──────────────────────────────────────────────────────────────

class BaseDetector:
    def __init__(self, reasoning: ReasoningEngine):
        self._reasoning = reasoning

    def detect(self, product, business_type: str) -> Optional[StructuredInsight]:
        raise NotImplementedError

    def _latest_burn(self, product):
        return product.burn_rates.order_by("-computed_at").first()

    def _recent_sales(self, product, days: int = 7):
        from apps.inventory.models import InventoryEvent
        return list(
            InventoryEvent.objects.filter(
                product=product,
                event_type=InventoryEvent.SALE,
                occurred_at__gte=timezone.now() - timedelta(days=days),
            )
        )


# ── Detectors ──────────────────────────────────────────────────────────────────

class StockRiskDetector(BaseDetector):
    """Fires when estimated stockout is within 14 days."""
    THRESHOLD_DAYS = 14

    def detect(self, product, business_type):
        burn = self._latest_burn(product)
        if not burn or burn.burn_rate_per_day <= 0:
            return None
        days = product.estimated_quantity / burn.burn_rate_per_day
        if days > self.THRESHOLD_DAYS:
            return None
        return self._reasoning.generate(product, "StockRiskDetector", {
            "stockout_days":       days,
            "confidence":          burn.confidence_score,
            "burn_rate":           burn.burn_rate_per_day,
            "estimated_quantity":  product.estimated_quantity,
        }, business_type)


class DemandShiftDetector(BaseDetector):
    """Fires when demand direction is not stable."""
    def detect(self, product, business_type):
        direction = getattr(product, "demand_direction", "stable")
        confidence = getattr(product, "demand_confidence", 0.0)
        if direction == "stable" or confidence < 0.35:
            return None
        burn = self._latest_burn(product)
        return self._reasoning.generate(product, "DemandShiftDetector", {
            "demand_direction": direction,
            "confidence":       confidence,
            "burn_rate":        burn.burn_rate_per_day if burn else 0,
        }, business_type)


class PatternDetector(BaseDetector):
    """Detects consistent weekly/monthly patterns."""
    def detect(self, product, business_type):
        from apps.inventory.models import InventoryEvent
        from collections import defaultdict

        events = list(
            InventoryEvent.objects.filter(
                product=product,
                event_type=InventoryEvent.SALE,
                occurred_at__gte=timezone.now() - timedelta(days=56),
            ).order_by("occurred_at")
        )
        if len(events) < 12:
            return None

        # Check for weekly pattern (weekday concentration)
        weekday_counts: dict = defaultdict(float)
        for e in events:
            weekday_counts[e.occurred_at.weekday()] += e.quantity

        total = sum(weekday_counts.values())
        if total <= 0:
            return None

        peak_day_share = max(weekday_counts.values()) / total
        if peak_day_share < 0.25:   # no clear pattern
            return None

        confidence = min(0.85, peak_day_share * 2)
        return self._reasoning.generate(product, "PatternDetector", {
            "confidence":   confidence,
            "pattern_type": "weekly",
            "burn_rate":    getattr(self._latest_burn(product), "burn_rate_per_day", 0),
        }, business_type)


class ProfitRiskDetector(BaseDetector):
    """Fires when stock is excessive relative to consumption rate."""
    OVERSTOCK_DAYS = 45

    def detect(self, product, business_type):
        burn = self._latest_burn(product)
        if not burn or burn.burn_rate_per_day <= 0:
            return None
        days_of_stock = product.estimated_quantity / burn.burn_rate_per_day
        if days_of_stock < self.OVERSTOCK_DAYS:
            return None
        if burn.confidence_score < 0.4:
            return None
        return self._reasoning.generate(product, "ProfitRiskDetector", {
            "stockout_days":      days_of_stock,
            "confidence":         burn.confidence_score,
            "burn_rate":          burn.burn_rate_per_day,
            "estimated_quantity": product.estimated_quantity,
        }, business_type)


class DataQualityDetector(BaseDetector):
    """Fires when confidence is too low for reliable decisions."""
    CONFIDENCE_FLOOR = 0.30

    def detect(self, product, business_type):
        if product.confidence_score >= self.CONFIDENCE_FLOOR:
            return None
        return self._reasoning.generate(product, "DataQualityDetector", {
            "confidence": product.confidence_score,
        }, business_type)


class AnomalyDetector(BaseDetector):
    """Detects unexpected spikes or drops vs historical average."""
    ANOMALY_THRESHOLD = 0.60   # 60% deviation

    def detect(self, product, business_type):
        burn = self._latest_burn(product)
        if not burn or burn.burn_rate_per_day <= 0:
            return None

        recent = self._recent_sales(product, days=3)
        if not recent:
            return None

        recent_rate = sum(e.quantity for e in recent) / 3.0
        expected    = burn.burn_rate_per_day
        drift       = (recent_rate - expected) / max(expected, 0.001)

        if abs(drift) < self.ANOMALY_THRESHOLD:
            return None

        confidence = min(0.80, abs(drift))
        return self._reasoning.generate(product, "AnomalyDetector", {
            "confidence":         confidence,
            "drift_pct":          drift * 100,
            "burn_rate":          expected,
            "estimated_quantity": product.estimated_quantity,
        }, business_type)


class OpportunityDetector(BaseDetector):
    """Fires when demand is rising and stock is moderate (undersupply risk)."""
    def detect(self, product, business_type):
        direction  = getattr(product, "demand_direction", "stable")
        dem_conf   = getattr(product, "demand_confidence", 0.0)
        if direction != "increasing" or dem_conf < 0.40:
            return None

        burn = self._latest_burn(product)
        if not burn:
            return None

        days_of_stock = product.estimated_quantity / max(burn.burn_rate_per_day, 0.01)
        if days_of_stock > 20:   # plenty of stock — no opportunity
            return None

        return self._reasoning.generate(product, "OpportunityDetector", {
            "confidence":         dem_conf * 0.9,
            "demand_direction":   direction,
            "burn_rate":          burn.burn_rate_per_day,
            "estimated_quantity": product.estimated_quantity,
            "opportunity_type":   "restock",
        }, business_type)