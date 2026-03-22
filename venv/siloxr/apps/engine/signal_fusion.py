# backend/apps/engine/signal_fusion.py

"""
Signal Fusion Engine.

Unifies two independent evidence streams into a single
estimated_demand value with a composite confidence score.

Stream 1 — Sales signals (direct):
  Data comes from SALE InventoryEvents.
  Quality scored via Sales Reliability Score (SRS).

Stream 2 — Inventory signals (indirect):
  Data comes from estimated_quantity drift vs STOCK_COUNT events.
  Quality scored via Inventory Reliability Score (IRS).

The weight each stream receives is proportional to its reliability.
This means a product with frequent physical counts but sparse sale
recording will be primarily driven by the inventory stream — and
vice versa.

STOCKOUT PROTECTION:
When stock hits zero, demand is NOT dropped to zero. Zero stock
does not mean zero demand — it means demand was not observable.
The stockout_flag is set and the Forecast Engine handles urgency.
"""

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Output dataclass ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FusionResult:
    """
    Full output of a signal fusion cycle for one product.
    Consumed by the Forecast Engine and Decision Engine.
    """
    estimated_demand:    float    # units/day — the primary output
    confidence_score:    float    # 0.05–0.99
    srs:                 float    # Sales Reliability Score (0–1)
    irs:                 float    # Inventory Reliability Score (0–1)
    sales_weight:        float    # proportion of demand from sales stream
    inventory_weight:    float    # proportion of demand from inventory stream
    avg_daily_sales:     float    # raw sales-derived burn rate
    inferred_burn_rate:  float    # raw inventory-derived burn rate
    conflict_ratio:      float    # how much the two streams disagree
    stockout_flag:       bool     # True if stock is currently at zero
    reasoning:           str      # human-readable fusion summary


# ── Sub-scorers ────────────────────────────────────────────────────────────────

class SalesReliabilityScorer:
    """
    SRS = 0.4 * data_completeness + 0.3 * recency + 0.2 * consistency + 0.1 * volume
    """

    def score(self, product, window_days: int = 30) -> tuple[float, float]:
        """Returns (srs, avg_daily_sales)."""
        from apps.inventory.models import InventoryEvent

        window_start = timezone.now() - timedelta(days=window_days)
        sale_events  = list(
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.SALE,
                occurred_at__gte=window_start,
            )
            .order_by("occurred_at")
        )

        count = len(sale_events)

        if count == 0:
            return 0.05, 0.0

        total_sold      = sum(e.quantity for e in sale_events)
        avg_daily_sales = total_sold / window_days

        data_completeness = self._completeness(count, window_days)
        recency           = self._recency(sale_events)
        consistency       = self._consistency(sale_events, window_days)
        volume            = self._volume(count)

        srs = (
            0.4 * data_completeness +
            0.3 * recency +
            0.2 * consistency +
            0.1 * volume
        )

        return round(max(0.05, min(1.0, srs)), 4), round(avg_daily_sales, 4)

    def _completeness(self, count: int, window_days: int) -> float:
        """Fraction of days in the window that had at least one sale recorded."""
        # Using a log scale — 1 sale = low completeness, 30 sales in 30 days = full
        expected = window_days * 0.5  # expect sales on ~50% of days
        return min(1.0, count / expected)

    def _recency(self, events: list) -> float:
        """Exponential decay from most recent event."""
        if not events:
            return 0.0
        days_ago = max(0.0, (timezone.now() - events[-1].occurred_at).total_seconds() / 86400)
        k = -math.log(0.05) / 30
        return math.exp(-k * days_ago)

    def _consistency(self, events: list, window_days: int) -> float:
        """How evenly distributed are sales across the window?"""
        if len(events) < 3:
            return 0.2
        # Bucket by day and compute CV of daily quantities
        from collections import defaultdict
        daily: dict[object, float] = defaultdict(float)
        for e in events:
            daily[e.occurred_at.date()] += e.quantity
        values = list(daily.values())
        if not values or statistics.mean(values) <= 0:
            return 0.2
        cv = statistics.stdev(values) / statistics.mean(values) if len(values) > 1 else 1.0
        return max(0.1, min(1.0, 1.0 - cv / 2.0))

    def _volume(self, count: int) -> float:
        """Logarithmic volume score — 30+ events = full."""
        return min(1.0, math.log1p(count) / math.log1p(30))


class InventoryReliabilityScorer:
    """
    IRS = 0.35 * count_frequency + 0.25 * drift_accuracy + 0.25 * recency + 0.15 * stability
    """

    def score(self, product, window_days: int = 30) -> tuple[float, float]:
        """Returns (irs, inferred_burn_rate)."""
        from apps.inventory.models import BurnRate, InventoryEvent

        window_start = timezone.now() - timedelta(days=window_days)
        count_events = list(
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.STOCK_COUNT,
                occurred_at__gte=window_start,
                verified_quantity__isnull=False,
            )
            .order_by("occurred_at")
        )

        # Use latest BurnRate as the base inferred rate
        burn = (
            BurnRate.objects
            .filter(product=product)
            .order_by("-computed_at")
            .first()
        )
        inferred_rate = burn.burn_rate_per_day if burn else 0.0

        if not count_events:
            # No physical counts — IRS is low but not zero
            return 0.15, inferred_rate

        count_frequency = self._count_frequency(len(count_events), window_days)
        drift_accuracy  = self._drift_accuracy(count_events, product)
        recency         = self._recency(count_events)
        stability       = burn.confidence_score if burn else 0.1

        irs = (
            0.35 * count_frequency +
            0.25 * drift_accuracy +
            0.25 * recency +
            0.15 * stability
        )

        return round(max(0.05, min(1.0, irs)), 4), round(inferred_rate, 4)

    def _count_frequency(self, count: int, window_days: int) -> float:
        """1 count/month = 0.5, 4+ counts/month = 1.0."""
        rate = count / (window_days / 30)
        return min(1.0, rate / 4.0)

    def _drift_accuracy(self, count_events: list, product) -> float:
        """
        How close were our estimates to actual counts?
        Small drift = high accuracy.
        """
        drifts = []
        for e in count_events:
            if e.verified_quantity is None:
                continue
            # signed_quantity encodes the delta that was revealed
            delta = abs(e.signed_quantity)
            base  = max(1.0, abs(e.verified_quantity))
            drifts.append(min(1.0, delta / base))

        if not drifts:
            return 0.5

        avg_drift = statistics.mean(drifts)
        return max(0.0, min(1.0, 1.0 - avg_drift))

    def _recency(self, count_events: list) -> float:
        """Decay from most recent count."""
        if not count_events:
            return 0.0
        days_ago = max(0.0, (timezone.now() - count_events[-1].occurred_at).total_seconds() / 86400)
        k = -math.log(0.05) / 45   # slower decay for counts (they're less frequent)
        return math.exp(-k * days_ago)


# ── Main engine ────────────────────────────────────────────────────────────────

class SignalFusionEngine:
    """
    Fuses sales and inventory signals into a unified demand estimate.

    Called by the Learning Engine after BurnRate is computed.
    The result flows into the Forecast Engine replacing the raw burn rate.
    """

    CONFLICT_THRESHOLD  = 0.40   # 40% mismatch triggers penalty
    STOCKOUT_ZERO_FLOOR = 0.5    # minimum demand when stock is zero

    def fuse(self, product, window_days: int = 30) -> FusionResult:
        """Execute a full signal fusion cycle for one product."""

        srs_scorer = SalesReliabilityScorer()
        irs_scorer = InventoryReliabilityScorer()

        srs, avg_daily_sales    = srs_scorer.score(product, window_days)
        irs, inferred_burn_rate = irs_scorer.score(product, window_days)

        # ── Conflict detection ─────────────────────────────────────────────
        conflict_ratio = self._conflict_ratio(avg_daily_sales, inferred_burn_rate)

        if conflict_ratio > self.CONFLICT_THRESHOLD:
            penalty    = min(0.5, conflict_ratio)
            srs_adj    = srs * (1 - penalty)
            irs_adj    = irs * (1 - penalty * 0.5)
            logger.info(
                "Signal conflict for %s: %.0f%% mismatch — SRS %.3f→%.3f, IRS %.3f→%.3f",
                product.sku, conflict_ratio * 100, srs, srs_adj, irs, irs_adj,
            )
            srs = srs_adj
            irs = irs_adj

        # ── Weighting ──────────────────────────────────────────────────────
        total = srs + irs
        if total <= 0:
            sales_weight = inventory_weight = 0.5
        else:
            sales_weight     = srs / total
            inventory_weight = irs / total

        # ── Demand estimation ──────────────────────────────────────────────
        estimated_demand = (
            sales_weight     * avg_daily_sales +
            inventory_weight * inferred_burn_rate
        )

        # ── Stockout protection ────────────────────────────────────────────
        stockout_flag = product.estimated_quantity <= 0
        if stockout_flag:
            # Zero stock ≠ zero demand — demand was unobservable, not absent
            estimated_demand = max(
                estimated_demand,
                (avg_daily_sales + inferred_burn_rate) / 2 * self.STOCKOUT_ZERO_FLOOR,
            )

        estimated_demand = max(0.01, estimated_demand)

        # ── Confidence ─────────────────────────────────────────────────────
        confidence = (
            0.6 * max(srs, irs) +
            0.4 * (1.0 - conflict_ratio)
        )
        confidence = max(0.05, min(0.99, confidence))

        reasoning = self._build_reasoning(
            product, srs, irs, sales_weight, conflict_ratio, stockout_flag
        )

        result = FusionResult(
            estimated_demand   = round(estimated_demand, 4),
            confidence_score   = round(confidence, 4),
            srs                = round(srs, 4),
            irs                = round(irs, 4),
            sales_weight       = round(sales_weight, 4),
            inventory_weight   = round(inventory_weight, 4),
            avg_daily_sales    = round(avg_daily_sales, 4),
            inferred_burn_rate = round(inferred_burn_rate, 4),
            conflict_ratio     = round(conflict_ratio, 4),
            stockout_flag      = stockout_flag,
            reasoning          = reasoning,
        )

        logger.info(
            "Fusion for %s: demand=%.3f conf=%.0f%% srs=%.2f irs=%.2f conflict=%.0f%%",
            product.sku,
            estimated_demand,
            confidence * 100,
            srs, irs,
            conflict_ratio * 100,
        )

        return result

    def _conflict_ratio(self, sales_rate: float, inventory_rate: float) -> float:
        """Normalised absolute difference between the two rate estimates."""
        if sales_rate <= 0 and inventory_rate <= 0:
            return 0.0
        max_rate = max(sales_rate, inventory_rate, 0.001)
        return min(1.0, abs(sales_rate - inventory_rate) / max_rate)

    def _build_reasoning(
        self, product, srs: float, irs: float,
        sales_weight: float, conflict_ratio: float,
        stockout_flag: bool,
    ) -> str:
        dominant = "sales data" if sales_weight >= 0.5 else "inventory movement"
        parts = [f"Demand estimate for {product.sku} is primarily driven by {dominant}."]

        if conflict_ratio > self.CONFLICT_THRESHOLD:
            parts.append(
                f"Sales and inventory signals show notable disagreement "
                f"({conflict_ratio:.0%}), reducing overall confidence."
            )
        if stockout_flag:
            parts.append(
                "Stock is currently at or near zero. "
                "Demand is estimated from historical patterns."
            )
        return " ".join(parts)