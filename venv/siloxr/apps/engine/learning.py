# backend/apps/engine/learning.py

import logging
import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Avg, Count, F, FloatField, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.inventory.models import BurnRate, InventoryEvent, Product
from .confidence import ConfidenceScorer
from .bootstrap import BusinessTypeBaselineService
from apps.core.baselines import NigeriaBaselineService

logger = logging.getLogger(__name__)


@dataclass
class LearningResult:
    """
    Structured output of a single learning cycle.
    Returned to callers so they can inspect or log the outcome.
    """
    product_id: str
    burn_rate_per_day: float
    burn_rate_std_dev: float
    confidence_score: float
    sample_days: int
    sample_event_count: int
    window_days: int
    correction_applied: bool
    correction_magnitude: float   # How much the STOCK_COUNT shifted our estimate
    is_anomaly: bool = False
    skipped: bool = False
    skip_reason: str = ""


class LearningEngine:
    """
    Learns the burn rate for a product by analysing its InventoryEvent history.

    Core algorithm:
    1. Pull SALE events in the learning window (default: 30 days)
    2. Bucket sales by day to get a daily consumption series
    3. Compute mean and std dev of daily consumption
    4. Detect if recent STOCK_COUNT events reveal systematic drift
    5. Apply a drift correction if warranted
    6. Score confidence from four independent signals
    7. Write a new BurnRate record
    8. Update Product.confidence_score

    The engine is designed to be called:
    - After every SALE event (lightweight, incremental)
    - After every STOCK_COUNT event (full recalculation with correction)
    - On a daily schedule for all active products
    """

    # Learning window in days. 30 days balances recency vs sample size.
    DEFAULT_WINDOW_DAYS = 30

    # Minimum events needed before we write a burn rate.
    # Below this we write a record but flag low confidence.
    MIN_EVENTS_FOR_ESTIMATE = 3

    # Correction: if STOCK_COUNT reveals drift above this threshold,
    # we adjust the burn rate estimate proportionally.
    CORRECTION_DRIFT_THRESHOLD = 0.10   # 10% drift triggers correction
    WINSORIZE_LOWER_QUANTILE = 0.05
    WINSORIZE_UPPER_QUANTILE = 0.95
    RECENCY_HALF_LIFE_DAYS = 14.0

    def __init__(self, window_days: int = DEFAULT_WINDOW_DAYS):
        self.window_days = window_days
        self.scorer = ConfidenceScorer()

    def run(self, product: Product) -> LearningResult:
        """
        Execute a full learning cycle for one product.
        Writes a BurnRate record and updates the product's confidence_score.
        """
        logger.debug("Learning cycle started for product: %s", product.sku)

        window_start = timezone.now() - timedelta(days=self.window_days)

        # ── Step 1: Pull relevant events ─────────────────────────────────
        sale_events = (
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.SALE,
                occurred_at__gte=window_start,
            )
            .order_by("occurred_at")
        )

        stock_count_events = (
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.STOCK_COUNT,
                occurred_at__gte=window_start,
            )
            .order_by("occurred_at")
        )

        event_count = sale_events.count()

        if event_count == 0:
            return self._handle_no_data(product)

        # ── Step 2: Build daily consumption buckets ───────────────────────
        daily_totals = self._aggregate_daily_sales(sale_events)
        all_days_in_window = self._fill_zero_days(daily_totals, window_start)

        # ── Step 3: Compute mean and std dev ─────────────────────────────
        demand_stats = self._estimate_demand_stats(product, all_days_in_window)
        burn_rate_per_day = demand_stats["mean"]
        burn_rate_std_dev = demand_stats["std_dev"]
        is_anomaly = demand_stats.get("is_anomaly", False)

        # ── Step 4: STOCK_COUNT correction ───────────────────────────────
        correction_applied = False
        correction_magnitude = 0.0
        avg_drift_pct = 0.0

        if stock_count_events.exists():
            correction_result = self._apply_stock_count_correction(
                product=product,
                burn_rate_per_day=burn_rate_per_day,
                stock_count_events=stock_count_events,
            )
            burn_rate_per_day = correction_result["adjusted_rate"]
            correction_applied = correction_result["applied"]
            correction_magnitude = correction_result["magnitude"]
            avg_drift_pct = correction_result["avg_drift_pct"]

        # ── Step 5: Score confidence ──────────────────────────────────────
        last_event = sale_events.last()
        components = self.scorer.compute(
            last_event_date=last_event.occurred_at if last_event else None,
            sample_event_count=event_count,
            burn_rate_std_dev=burn_rate_std_dev,
            burn_rate_per_day=burn_rate_per_day,
            avg_drift_pct=avg_drift_pct,
        )

        # ── Step 6: Persist and update product ───────────────────────────
        burn_rate = self._write_burn_rate(
            product=product,
            burn_rate_per_day=burn_rate_per_day,
            burn_rate_std_dev=burn_rate_std_dev,
            confidence_score=components.final_score,
            sample_days=len(all_days_in_window),
            sample_event_count=event_count,
        )

        self._update_product_confidence(product, components.final_score)

        result = LearningResult(
            product_id=str(product.id),
            burn_rate_per_day=burn_rate_per_day,
            burn_rate_std_dev=burn_rate_std_dev,
            confidence_score=components.final_score,
            sample_days=len(all_days_in_window),
            sample_event_count=event_count,
            window_days=self.window_days,
            correction_applied=correction_applied,
            correction_magnitude=correction_magnitude,
            is_anomaly=is_anomaly,
        )

        logger.info(
            "Learning complete for %s: %.3f/day ±%.3f, conf=%.0f%%, correction=%s",
            product.sku,
            burn_rate_per_day,
            burn_rate_std_dev,
            components.final_score * 100,
            f"{correction_magnitude:+.1%}" if correction_applied else "none",
        )

        return result

    def run_for_all_active(self) -> list[LearningResult]:
        """
        Run learning for all active products owned by any user.
        Used by the daily scheduled task.
        Returns a list of results for monitoring.
        """
        products = Product.objects.filter(is_active=True).select_related("owner")
        results = []
        for product in products:
            try:
                result = self.run(product)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Learning failed for product %s: %s", product.sku, exc,
                    exc_info=True,
                )
        return results

    # ── Private helpers ───────────────────────────────────────────────────

    def _aggregate_daily_sales(self, sale_events) -> dict[date, float]:
        """
        Group sale quantities by calendar day.
        Returns {date: total_units_sold}.
        """
        daily = {}
        for event in sale_events:
            day = event.occurred_at.date()
            daily[day] = daily.get(day, 0.0) + event.quantity
        return daily

    def _fill_zero_days(
        self, daily_totals: dict[date, float], window_start: datetime
    ) -> list[float]:
        """
        Fill in zero-consumption days within the window.
        This is critical: days with no sales still happened.
        Omitting them would overestimate the burn rate.

        Returns a flat list of daily consumption values.
        """
        today = timezone.now().date()
        start_date = window_start.date()

        all_days = []
        current = start_date
        while current <= today:
            all_days.append(daily_totals.get(current, 0.0))
            current += timedelta(days=1)

        return all_days

    def _estimate_demand_stats(self, product: Product, daily_series: list[float]) -> dict[str, float]:
        """
        Robust small-sample demand estimation for production operations.

        We keep zero-demand days, winsorize extreme outliers, and weight
        recent days more heavily to better reflect current operating reality.
        """
        if not daily_series:
            return {"mean": 0.0, "std_dev": 0.0, "is_anomaly": False}

        baseline = self._baseline_prior(product)
        anomaly_pass = self._cap_anomalies(daily_series)
        cleansed = self._winsorize_series(anomaly_pass["series"])
        weighted = self._weighted_mean_std(cleansed)
        blended = self._blend_with_prior(
            learned_mean=weighted["mean"],
            learned_std=weighted["std_dev"],
            prior_mean=baseline["burn_rate_per_day"],
            prior_std=baseline["burn_rate_std_dev"],
            n=len([v for v in daily_series if v > 0]),
            days=len(daily_series),
        )
        return {
            "mean": round(blended["mean"], 4),
            "std_dev": round(blended["std_dev"], 4),
            "is_anomaly": anomaly_pass["is_anomaly"],
        }

    def _baseline_prior(self, product: Product) -> dict[str, float]:
        # The prior keeps early-stage products anchored to realistic demand bands.
        baseline = NigeriaBaselineService().for_product(product)
        if baseline:
            return {
                "burn_rate_per_day": max(0.01, float(baseline["daily_demand"])),
                "burn_rate_std_dev": max(0.01, float(baseline["demand_std"]) / 7.0),
                "confidence_score": 0.26,
                "assumptions_summary": baseline["message"],
            }
        return BusinessTypeBaselineService().derive_seed_burn(product)

    def _blend_with_prior(
        self,
        *,
        learned_mean: float,
        learned_std: float,
        prior_mean: float,
        prior_std: float,
        n: int,
        days: int,
    ) -> dict[str, float]:
        burn_rate_weight = min(n / 7.0, 1.0)
        variance_weight = min(n / 10.0, 1.0)
        seasonality_weight = min(days / 28.0, 1.0)

        final_mean = (burn_rate_weight * learned_mean) + ((1.0 - burn_rate_weight) * prior_mean)
        combined_weight = min(1.0, (variance_weight * 0.7) + (seasonality_weight * 0.3))
        final_std = (combined_weight * learned_std) + ((1.0 - combined_weight) * prior_std)
        return {
            "mean": max(0.0, final_mean),
            "std_dev": max(0.0, final_std),
        }

    def _cap_anomalies(self, series: list[float]) -> dict[str, object]:
        if len(series) < 2:
            return {"series": [max(0.0, float(v)) for v in series], "is_anomaly": False}

        base = [max(0.0, float(v)) for v in series]
        mean = statistics.mean(base)
        std = statistics.pstdev(base) if len(base) > 1 else 0.0
        upper = mean + (2.5 * std)
        is_anomaly = any(v > upper for v in base) if std > 0 else False
        return {
            "series": [min(v, upper) if std > 0 else v for v in base],
            "is_anomaly": is_anomaly,
        }

    def _winsorize_series(self, series: list[float]) -> list[float]:
        if len(series) < 5:
            return [max(0.0, float(v)) for v in series]

        ordered = sorted(max(0.0, float(v)) for v in series)
        lower = self._percentile(ordered, self.WINSORIZE_LOWER_QUANTILE)
        upper = self._percentile(ordered, self.WINSORIZE_UPPER_QUANTILE)
        return [min(max(max(0.0, float(v)), lower), upper) for v in series]

    def _percentile(self, ordered: list[float], q: float) -> float:
        if not ordered:
            return 0.0
        if len(ordered) == 1:
            return ordered[0]

        position = (len(ordered) - 1) * q
        lower_idx = int(math.floor(position))
        upper_idx = int(math.ceil(position))
        if lower_idx == upper_idx:
            return ordered[lower_idx]

        weight = position - lower_idx
        return ordered[lower_idx] * (1.0 - weight) + ordered[upper_idx] * weight

    def _weighted_mean_std(self, series: list[float]) -> dict[str, float]:
        if not series:
            return {"mean": 0.0, "std_dev": 0.0}

        weights: list[float] = []
        for idx in range(len(series)):
            days_ago = len(series) - idx - 1
            weights.append(0.5 ** (days_ago / self.RECENCY_HALF_LIFE_DAYS))

        total_weight = sum(weights) or 1.0
        mean = sum(v * w for v, w in zip(series, weights)) / total_weight
        variance = sum(w * ((v - mean) ** 2) for v, w in zip(series, weights)) / total_weight
        return {
            "mean": max(0.0, mean),
            "std_dev": max(0.0, math.sqrt(max(0.0, variance))),
        }

    def _apply_stock_count_correction(
        self,
        product: Product,
        burn_rate_per_day: float,
        stock_count_events,
    ) -> dict:
        """
        Analyse STOCK_COUNT events to detect and correct systematic bias
        in our burn rate estimate.

        Logic:
        - For each STOCK_COUNT event, compute the drift:
          drift = (verified_quantity - estimated_quantity_before_count) / estimated_quantity_before_count
        - If the average drift exceeds CORRECTION_DRIFT_THRESHOLD,
          the burn rate was too high or too low and we adjust.

        A positive drift (more stock than expected) means we're over-estimating burn rate.
        A negative drift (less stock than expected) means we're under-estimating.
        """
        drift_values = []

        for event in stock_count_events:
            if event.verified_quantity is None:
                continue

            # Estimate what quantity should have been just before this count
            # We use the event's signed_quantity as the delta the count revealed
            estimated_before = (
                event.verified_quantity - event.signed_quantity
            )

            if estimated_before <= 0:
                continue

            drift = (event.verified_quantity - estimated_before) / estimated_before
            drift_values.append(drift)

        if not drift_values:
            return {
                "adjusted_rate": burn_rate_per_day,
                "applied": False,
                "magnitude": 0.0,
                "avg_drift_pct": 0.0,
            }

        avg_drift = statistics.mean(drift_values)
        avg_drift_pct = abs(avg_drift)

        # Only correct if drift is meaningful
        if avg_drift_pct < self.CORRECTION_DRIFT_THRESHOLD:
            return {
                "adjusted_rate": burn_rate_per_day,
                "applied": False,
                "magnitude": avg_drift_pct,
                "avg_drift_pct": avg_drift_pct,
            }

        # Adjust: if we over-counted stock (positive drift), burn rate was too high
        # Correction factor dampened to 50% of drift to avoid overcorrection
        correction_factor = 1.0 - (avg_drift * 0.5)
        adjusted_rate = max(0.01, burn_rate_per_day * correction_factor)

        logger.info(
            "Burn rate correction applied for %s: %.3f → %.3f (drift=%.1f%%)",
            product.sku,
            burn_rate_per_day,
            adjusted_rate,
            avg_drift * 100,
        )

        return {
            "adjusted_rate": adjusted_rate,
            "applied": True,
            "magnitude": avg_drift_pct,
            "avg_drift_pct": avg_drift_pct,
        }

    @transaction.atomic
    def _write_burn_rate(
        self,
        product: Product,
        burn_rate_per_day: float,
        burn_rate_std_dev: float,
        confidence_score: float,
        sample_days: int,
        sample_event_count: int,
    ) -> BurnRate:
        return BurnRate.objects.create(
            product=product,
            burn_rate_per_day=round(burn_rate_per_day, 4),
            burn_rate_std_dev=round(burn_rate_std_dev, 4),
            confidence_score=round(confidence_score, 4),
            sample_days=sample_days,
            sample_event_count=sample_event_count,
            window_days=self.window_days,
        )

    def _update_product_confidence(
        self, product: Product, confidence_score: float
    ) -> None:
        """
        Propagate the latest confidence score back to the product.
        This is what drives UI indicators and decision thresholds.
        """
        Product.objects.filter(pk=product.pk).update(
            confidence_score=round(confidence_score, 4)
        )
        # Keep the in-memory object in sync
        product.confidence_score = round(confidence_score, 4)

    def _handle_no_data(self, product: Product) -> LearningResult:
        """
        No sale events in the window. We still write a record so the
        Forecast Engine has something to read — it will produce a
        low-confidence forecast rather than crashing.
        """
        logger.warning(
            "No sale events in window for %s — writing zero burn rate", product.sku
        )

        # Check if there's any historical burn rate to fall back on
        previous = (
            BurnRate.objects
            .filter(product=product)
            .order_by("-computed_at")
            .first()
        )

        baseline = NigeriaBaselineService().for_product(product)
        if baseline:
            fallback_rate = float(baseline["daily_demand"])
            fallback_std = float(baseline["demand_std"]) / 7.0
            fallback_confidence = 0.24
            skip_reason = baseline["message"]
        else:
            fallback_rate = previous.burn_rate_per_day * 0.5 if previous else 0.0
            fallback_std = 0.0
            fallback_confidence = previous.confidence_score * 0.5 if previous else 0.05
            skip_reason = "No sale events in learning window."

        self._write_burn_rate(
            product=product,
            burn_rate_per_day=fallback_rate,
            burn_rate_std_dev=fallback_std,
            confidence_score=min(fallback_confidence, 0.2),
            sample_days=0,
            sample_event_count=0,
        )
        final_confidence = min(fallback_confidence, 0.2)
        self._update_product_confidence(product, final_confidence)
        return LearningResult(
            product_id=str(product.id),
            burn_rate_per_day=round(fallback_rate, 4),
            burn_rate_std_dev=round(fallback_std, 4),
            confidence_score=round(final_confidence, 4),
            sample_days=0,
            sample_event_count=0,
            window_days=self.window_days,
            correction_applied=False,
            correction_magnitude=0.0,
            skipped=True,
            skip_reason=skip_reason,
        )
# backend/apps/engine/learning.py
# ADD after _write_burn_rate() in run() — replace return block

        # ── Signal Fusion (runs after burn rate is computed) ──────────────
        from apps.engine.signal_fusion import SignalFusionEngine
        fusion = SignalFusionEngine().fuse(product)

        # Update product with fused demand estimate and confidence
        from apps.inventory.models import Product as ProductModel
        ProductModel.objects.filter(pk=product.pk).update(
            confidence_score    = fusion.confidence_score,
            data_maturity_score = maturity.final_score,
        )
        product.confidence_score = fusion.confidence_score

        # Store fusion result on the BurnRate for downstream engines to use
        # We piggyback on burn_rate_per_day with the fused demand estimate
        BurnRate.objects.filter(pk=burn_rate.pk).update(
            burn_rate_per_day = fusion.estimated_demand,
        )

        result = LearningResult(
            product_id         = str(product.id),
            burn_rate_per_day  = fusion.estimated_demand,
            burn_rate_std_dev  = burn_rate_std_dev,
            confidence_score   = fusion.confidence_score,
            sample_days        = len(all_days_in_window),
            sample_event_count = event_count,
            window_days        = self.window_days,
            correction_applied = correction_applied,
            correction_magnitude = correction_magnitude,
        )
        return result
