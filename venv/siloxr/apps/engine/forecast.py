# backend/apps/engine/forecast.py

import logging
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.inventory.models import BurnRate, ForecastSnapshot, Product
from apps.core.statistics import compute_cv, get_distribution_params
from apps.core.baselines import NigeriaBaselineService

logger = logging.getLogger(__name__)


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DailyProjection:
    """
    A single day's projected inventory state.
    This is the atomic unit the ProjectionBuilder produces.
    """
    forecast_date: date
    predicted_quantity: float     # Central estimate
    lower_bound: float            # Pessimistic (higher burn scenario)
    upper_bound: float            # Optimistic (lower burn scenario)
    confidence_score: float
    days_from_now: int


@dataclass
class ForecastResult:
    """
    Full output of a forecast run for one product.
    Returned to callers (Decision Engine, API, tasks).
    Snapshots are already persisted by the time this is returned.
    """
    product_id: str
    product_sku: str
    horizon_days: int
    projections: list[DailyProjection] = field(default_factory=list)

    # Key derived signals — pre-computed for the Decision Engine
    days_until_stockout: Optional[float] = None         # Central estimate
    days_until_stockout_pessimistic: Optional[float] = None  # Lower bound path
    stockout_range: list[Optional[float]] = field(default_factory=lambda: [None, None])
    days_until_reorder_point: Optional[float] = None
    suggested_reorder_date: Optional[date] = None
    stockout_risk_score: float = 0.0  # 0.0 = no risk, 1.0 = certain stockout

    # Metadata
    burn_rate_used: float = 0.0
    burn_rate_std_dev: float = 0.0
    initial_quantity: float = 0.0
    confidence_score: float = 0.0
    skipped: bool = False
    skip_reason: str = ""

    @property
    def is_stockout_imminent(self) -> bool:
        """True when pessimistic path hits zero within 7 days."""
        if self.days_until_stockout_pessimistic is None:
            return False
        return self.days_until_stockout_pessimistic <= 7

    @property
    def forecast_summary(self) -> str:
        """Human-readable one-liner for notifications and decision reasoning."""
        if self.skipped:
            return f"Forecast unavailable: {self.skip_reason}"
        if self.days_until_stockout is None:
            return "Stock appears sufficient for the forecast horizon."
        conf_pct = int(self.confidence_score * 100)
        return (
            f"Stock may run out in ~{self.days_until_stockout:.0f} days "
            f"(pessimistic: {self.days_until_stockout_pessimistic:.0f} days). "
            f"Confidence: {conf_pct}%."
        )


# ── Sub-components ─────────────────────────────────────────────────────────────

class ProjectionBuilder:
    """
    Builds a day-by-day projection of inventory from today through horizon_days.

    Central estimate: quantity decreases by burn_rate_per_day each day.
    Lower bound:      uses burn_rate + 1 std dev (faster burn = less stock).
    Upper bound:      uses burn_rate - 1 std dev (slower burn = more stock).

    Confidence decays as we project further into the future — the further out
    we look, the more uncertainty compounds. Decay rate is proportional to
    the coefficient of variation of the burn rate.
    """

    # How steeply confidence decays per day beyond the first week.
    # Higher CV → faster decay.
    BASE_CONFIDENCE_DECAY_PER_DAY = 0.008

    def build(
        self,
        start_quantity: float,
        burn_rate_per_day: float,
        burn_rate_std_dev: float,
        base_confidence: float,
        horizon_days: int,
    ) -> list[DailyProjection]:
        """
        Returns a list of DailyProjection, one per day in the horizon.
        Quantities are floored at 0.0 — negative stock is meaningless here.
        """
        today = timezone.now().date()
        projections: list[DailyProjection] = []

        cv = compute_cv(burn_rate_per_day, burn_rate_std_dev)
        mean_rate, adj_std = get_distribution_params(
            burn_rate_per_day,
            burn_rate_std_dev,
            cv,
        )

        # Pessimistic burn: mean + 1σ
        pessimistic_rate = mean_rate + adj_std
        # Optimistic burn: mean − 1σ, floored at 0
        optimistic_rate = max(0.0, mean_rate - adj_std)

        # Confidence decay factor: higher variance = faster decay
        decay_rate = self.BASE_CONFIDENCE_DECAY_PER_DAY * (1.0 + cv)

        central_qty = start_quantity
        pessimistic_qty = start_quantity
        optimistic_qty = start_quantity

        for day_offset in range(1, horizon_days + 1):
            central_qty     = max(0.0, central_qty     - mean_rate)
            pessimistic_qty = max(0.0, pessimistic_qty - pessimistic_rate)
            optimistic_qty  = max(0.0, optimistic_qty  - optimistic_rate)

            # Confidence decays with time and variance
            day_confidence = base_confidence * math.exp(-decay_rate * day_offset)
            day_confidence = max(0.05, min(base_confidence, day_confidence))

            projections.append(DailyProjection(
                forecast_date=today + timedelta(days=day_offset),
                predicted_quantity=round(central_qty, 2),
                lower_bound=round(pessimistic_qty, 2),
                upper_bound=round(optimistic_qty, 2),
                confidence_score=round(day_confidence, 4),
                days_from_now=day_offset,
            ))

        return projections


class StockoutDetector:
    """
    Scans a projection series to find when each path hits zero.
    Returns days-until-zero for the central and pessimistic paths.
    """

    MIN_SIGMA = 0.25

    def _normal_cdf(self, z: float) -> float:
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    def detect(
        self, projections: list[DailyProjection]
    ) -> dict[str, Optional[float]]:
        """
        Returns:
            central:     days until central estimate hits zero (or None)
            pessimistic: days until pessimistic path hits zero (or None)
        """
        central_zero = None
        pessimistic_zero = None

        for proj in projections:
            if central_zero is None and proj.predicted_quantity <= 0:
                central_zero = float(proj.days_from_now)
            if pessimistic_zero is None and proj.lower_bound <= 0:
                pessimistic_zero = float(proj.days_from_now)

            # Both found — no need to continue
            if central_zero is not None and pessimistic_zero is not None:
                break

        return {
            "central": central_zero,
            "pessimistic": pessimistic_zero,
        }

    def compute_stockout_risk(
        self,
        days_until_stockout_pessimistic: Optional[float],
        days_until_stockout_central: Optional[float],
        confidence_score: float,
        current_quantity: float,
        burn_rate_per_day: float,
        burn_rate_std_dev: float,
        horizon_days: int,
    ) -> float:
        """
        A 0.0–1.0 score representing how likely and how soon a stockout is.

        Industry framing:
        - probability component: stockout probability under a normal-demand model
        - urgency component: how near the likely shortfall window is
        - confidence cap: low-confidence models should not overstate certainty
        """
        stock_on_hand = max(float(current_quantity or 0.0), 0.0)
        burn_rate = max(float(burn_rate_per_day or 0.0), 0.0)
        cv = compute_cv(burn_rate, max(float(burn_rate_std_dev or 0.0), 0.0))
        mean_rate, sigma_per_day = get_distribution_params(
            burn_rate,
            max(float(burn_rate_std_dev or 0.0), 0.0),
            cv,
        )

        if mean_rate <= 0:
            return 0.05

        risk_horizon = min(
            max(1, int(horizon_days or 1)),
            14 if days_until_stockout_pessimistic is not None else 30,
        )
        mu = mean_rate * risk_horizon
        sigma = max(self.MIN_SIGMA, sigma_per_day * math.sqrt(risk_horizon))
        z = (stock_on_hand - mu) / sigma
        stockout_probability = max(0.0, min(1.0, 1.0 - self._normal_cdf(z)))

        urgency_days = (
            days_until_stockout_pessimistic
            if days_until_stockout_pessimistic is not None
            else days_until_stockout_central
        )
        if urgency_days is None:
            urgency_score = max(0.0, 1.0 - (risk_horizon / 30.0))
        else:
            urgency_score = max(0.0, 1.0 - (min(float(urgency_days), 30.0) / 30.0))

        blended = (stockout_probability * 0.7) + (urgency_score * 0.3)
        max_risk = 0.65 + (max(0.0, min(1.0, confidence_score)) * 0.35)
        return round(min(blended, max_risk), 4)


class ReorderAdvisor:
    """
    Given projections and a product's reorder configuration,
    determines when the reorder point will be crossed and
    what the suggested reorder date is (accounting for lead time).
    """

    # Default lead time assumption when product has no explicit setting
    DEFAULT_LEAD_TIME_DAYS = 3

    def advise(
        self,
        projections: list[DailyProjection],
        reorder_point: float,
        lead_time_days: int = DEFAULT_LEAD_TIME_DAYS,
    ) -> dict[str, Optional[date | float]]:
        """
        Returns:
            days_until_reorder_point: days until central estimate crosses reorder_point
            suggested_reorder_date:   date to place the order (crossing day - lead_time)
        """
        if reorder_point <= 0:
            return {
                "days_until_reorder_point": None,
                "suggested_reorder_date": None,
            }

        days_until_crossing = None
        for proj in projections:
            if proj.predicted_quantity <= reorder_point:
                days_until_crossing = float(proj.days_from_now)
                break

        if days_until_crossing is None:
            return {
                "days_until_reorder_point": None,
                "suggested_reorder_date": None,
            }

        today = timezone.now().date()
        # Reorder must be placed lead_time_days before the crossing
        reorder_day_offset = max(0, int(days_until_crossing) - lead_time_days)
        suggested_reorder_date = today + timedelta(days=reorder_day_offset)

        return {
            "days_until_reorder_point": days_until_crossing,
            "suggested_reorder_date": suggested_reorder_date,
        }


# ── Main engine ────────────────────────────────────────────────────────────────

class ForecastEngine:
    """
    Orchestrates projection, uncertainty banding, stockout detection,
    and reorder advising into a complete ForecastResult.

    Writes ForecastSnapshot records to the database.
    The Decision Engine reads these snapshots to produce actions.

    Snapshot strategy:
    - We write one snapshot per day in the horizon (upsert).
    - "Upsert" because a product can be forecast multiple times per day
      (after each SALE event via Learning → Forecast chain).
      We update rather than accumulate duplicates.
    """

    DEFAULT_HORIZON_DAYS = 30
    # Granularity: write a snapshot every N days (not every single day)
    # to keep the table manageable. Key days are always written.
    SNAPSHOT_INTERVAL_DAYS = 1   # every day for the first 14 days
    FAR_HORIZON_INTERVAL = 3     # every 3 days beyond day 14

    def __init__(
        self,
        horizon_days: int = DEFAULT_HORIZON_DAYS,
        lead_time_days: int = ReorderAdvisor.DEFAULT_LEAD_TIME_DAYS,
    ):
        self.horizon_days = horizon_days
        self.lead_time_days = lead_time_days
        self._projector = ProjectionBuilder()
        self._stockout_detector = StockoutDetector()
        self._reorder_advisor = ReorderAdvisor()

    def _blend_with_baseline(self, product: Product, burn_rate: BurnRate) -> dict[str, float]:
        baseline = NigeriaBaselineService().for_product(product)
        if not baseline:
            return {
                "burn_rate_per_day": float(burn_rate.burn_rate_per_day),
                "burn_rate_std_dev": float(burn_rate.burn_rate_std_dev),
                "confidence_score": float(burn_rate.confidence_score),
                "baseline_used": False,
            }

        n = int(getattr(burn_rate, "sample_event_count", 0) or 0)
        days = int(getattr(burn_rate, "window_days", self.horizon_days) or self.horizon_days)
        burn_rate_weight = min(n / 7.0, 1.0)
        variance_weight = min(n / 10.0, 1.0)
        seasonality_weight = min(days / 28.0, 1.0)
        confidence_weight = min(1.0, (burn_rate_weight * 0.6) + (seasonality_weight * 0.4))

        baseline_daily = float(baseline["daily_demand"])
        baseline_std_daily = float(baseline["demand_std"]) / 7.0
        blended_rate = (burn_rate_weight * float(burn_rate.burn_rate_per_day)) + ((1.0 - burn_rate_weight) * baseline_daily)
        blended_std = (variance_weight * float(burn_rate.burn_rate_std_dev)) + ((1.0 - variance_weight) * baseline_std_daily)
        blended_confidence = (confidence_weight * float(burn_rate.confidence_score)) + ((1.0 - confidence_weight) * 0.26)
        return {
            "burn_rate_per_day": round(blended_rate, 4),
            "burn_rate_std_dev": round(blended_std, 4),
            "confidence_score": round(blended_confidence, 4),
            "baseline_used": n < 7,
        }

    def run(self, product: Product) -> ForecastResult:
        """
        Execute a complete forecast for one product.
        Requires a BurnRate record to exist (Learning Engine must run first).
        """
        logger.debug("Forecast cycle started for product: %s", product.sku)

        # ── Fetch the latest burn rate ────────────────────────────────────
        burn_rate = (
            BurnRate.objects
            .filter(product=product)
            .order_by("-computed_at")
            .first()
        )

        if burn_rate is None:
            return self._seed_day_zero_forecast(product)

        if burn_rate.burn_rate_per_day <= 0:
            return self._handle_zero_burn_rate(product, burn_rate)

        blended = self._blend_with_baseline(product, burn_rate)

        # ── Build projections ─────────────────────────────────────────────
        projections = self._projector.build(
            start_quantity=product.estimated_quantity,
            burn_rate_per_day=blended["burn_rate_per_day"],
            burn_rate_std_dev=blended["burn_rate_std_dev"],
            base_confidence=blended["confidence_score"],
            horizon_days=self.horizon_days,
        )

        # ── Stockout detection ────────────────────────────────────────────
        stockout_info = self._stockout_detector.detect(projections)
        stockout_risk = self._stockout_detector.compute_stockout_risk(
            days_until_stockout_pessimistic=stockout_info["pessimistic"],
            days_until_stockout_central=stockout_info["central"],
            confidence_score=blended["confidence_score"],
            current_quantity=product.estimated_quantity,
            burn_rate_per_day=blended["burn_rate_per_day"],
            burn_rate_std_dev=blended["burn_rate_std_dev"],
            horizon_days=self.horizon_days,
        )

        # ── Reorder advising ──────────────────────────────────────────────
        reorder_info = self._reorder_advisor.advise(
            projections=projections,
            reorder_point=product.reorder_point,
            lead_time_days=self.lead_time_days,
        )

        # ── Persist snapshots ─────────────────────────────────────────────
        self._persist_snapshots(product, burn_rate, projections)

        result = ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=self.horizon_days,
            projections=projections,
            days_until_stockout=stockout_info["central"],
            days_until_stockout_pessimistic=stockout_info["pessimistic"],
            stockout_range=[stockout_info["pessimistic"], stockout_info["central"]],
            days_until_reorder_point=reorder_info["days_until_reorder_point"],
            suggested_reorder_date=reorder_info["suggested_reorder_date"],
            stockout_risk_score=stockout_risk,
            burn_rate_used=blended["burn_rate_per_day"],
            burn_rate_std_dev=blended["burn_rate_std_dev"],
            initial_quantity=product.estimated_quantity,
            confidence_score=blended["confidence_score"],
        )

        logger.info(
            "Forecast complete for %s: stockout in ~%.0fd (pessimistic: %.0fd), "
            "risk=%.0f%%, conf=%.0f%%",
            product.sku,
            stockout_info["central"] or 999,
            stockout_info["pessimistic"] or 999,
            stockout_risk * 100,
            blended["confidence_score"] * 100,
        )

        return result

    def run_for_all_active(self) -> list[ForecastResult]:
        """
        Run forecasts for all active products.
        Called by the daily scheduled task after the learning sweep completes.
        """
        products = Product.objects.filter(is_active=True).select_related("owner")
        results = []
        for product in products:
            try:
                result = self.run(product)
                results.append(result)
            except Exception as exc:
                logger.error(
                    "Forecast failed for product %s: %s",
                    product.sku, exc, exc_info=True,
                )
        return results

    # ── Private helpers ───────────────────────────────────────────────────────

    @transaction.atomic
    def _persist_snapshots(
        self,
        product: Product,
        burn_rate: BurnRate,
        projections: list[DailyProjection],
    ) -> None:
        """
        Upsert ForecastSnapshot records.

        Strategy: write every day for the near horizon (days 1–14),
        every 3 days for the far horizon (days 15–30).
        Always write day 1, day 7, day 14, day 30 regardless of interval.

        Key days are written regardless of interval so the UI always has
        reference points for weekly and monthly views.
        """
        key_offsets = {1, 7, 14, self.horizon_days}

        for proj in projections:
            should_write = (
                proj.days_from_now in key_offsets
                or (
                    proj.days_from_now <= 14
                    and proj.days_from_now % self.SNAPSHOT_INTERVAL_DAYS == 0
                )
                or (
                    proj.days_from_now > 14
                    and proj.days_from_now % self.FAR_HORIZON_INTERVAL == 0
                )
            )
            if not should_write:
                continue

            ForecastSnapshot.objects.update_or_create(
                product=product,
                forecast_date=proj.forecast_date,
                defaults={
                    "burn_rate": burn_rate,
                    "predicted_quantity": proj.predicted_quantity,
                    "lower_bound": proj.lower_bound,
                    "upper_bound": proj.upper_bound,
                    "confidence_score": proj.confidence_score,
                    # Reset actuals so the Feedback Engine re-evaluates
                    "actual_quantity": None,
                    "forecast_error": None,
                },
            )

    def _handle_no_burn_rate(self, product: Product) -> ForecastResult:
        logger.warning(
            "No burn rate found for %s — skipping forecast", product.sku
        )
        return ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=self.horizon_days,
            skipped=True,
            skip_reason="No burn rate available. Run the Learning Engine first.",
        )

    def _handle_zero_burn_rate(
        self, product: Product, burn_rate: BurnRate
    ) -> ForecastResult:
        """
        Zero burn rate means no sales were observed.
        We still produce a result — the stock is stable but the confidence is low.
        The Decision Engine will interpret this as CHECK_STOCK rather than HOLD.
        """
        logger.info(
            "Zero burn rate for %s — producing stable forecast", product.sku
        )

        today = timezone.now().date()
        projections = [
            DailyProjection(
                forecast_date=today + timedelta(days=d),
                predicted_quantity=product.estimated_quantity,
                lower_bound=product.estimated_quantity,
                upper_bound=product.estimated_quantity,
                confidence_score=burn_rate.confidence_score,
                days_from_now=d,
            )
            for d in range(1, self.horizon_days + 1)
        ]

        self._persist_snapshots(product, burn_rate, projections)

        return ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=self.horizon_days,
            projections=projections,
            days_until_stockout=None,
            days_until_stockout_pessimistic=None,
            stockout_range=[None, None],
            stockout_risk_score=0.05,
            burn_rate_used=0.0,
            burn_rate_std_dev=0.0,
            initial_quantity=product.estimated_quantity,
            confidence_score=burn_rate.confidence_score,
            skip_reason="Zero burn rate — no recent sales observed.",
        )

    def _seed_day_zero_forecast(self, product: Product) -> ForecastResult:
        """
        Day-zero bootstrap for products with no learned burn rate yet.
        Uses business-type priors so the system is useful from first use.
        """
        logger.info(
            "No burn rate found for %s - using industry baseline bootstrap",
            product.sku,
        )
        from apps.engine.bootstrap import BusinessTypeBaselineService

        seed = BusinessTypeBaselineService().derive_seed_burn(product)
        burn_rate = BurnRate.objects.create(
            product=product,
            burn_rate_per_day=seed["burn_rate_per_day"],
            burn_rate_std_dev=seed["burn_rate_std_dev"],
            confidence_score=seed["confidence_score"],
            sample_days=0,
            sample_event_count=0,
            window_days=30,
        )

        projections = self._projector.build(
            start_quantity=product.estimated_quantity,
            burn_rate_per_day=burn_rate.burn_rate_per_day,
            burn_rate_std_dev=burn_rate.burn_rate_std_dev,
            base_confidence=burn_rate.confidence_score,
            horizon_days=self.horizon_days,
        )
        stockout_info = self._stockout_detector.detect(projections)
        stockout_risk = self._stockout_detector.compute_stockout_risk(
            days_until_stockout_pessimistic=stockout_info["pessimistic"],
            days_until_stockout_central=stockout_info["central"],
            confidence_score=burn_rate.confidence_score,
            current_quantity=product.estimated_quantity,
            burn_rate_per_day=burn_rate.burn_rate_per_day,
            burn_rate_std_dev=burn_rate.burn_rate_std_dev,
            horizon_days=self.horizon_days,
        )
        reorder_info = self._reorder_advisor.advise(
            projections=projections,
            reorder_point=float(product.reorder_point),
            lead_time_days=self.lead_time_days,
        )
        self._persist_snapshots(product, burn_rate, projections)

        return ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=self.horizon_days,
            projections=projections,
            days_until_stockout=stockout_info["central"],
            days_until_stockout_pessimistic=stockout_info["pessimistic"],
            stockout_range=[stockout_info["pessimistic"], stockout_info["central"]],
            days_until_reorder_point=reorder_info["days_until_reorder_point"],
            suggested_reorder_date=reorder_info["suggested_reorder_date"],
            stockout_risk_score=stockout_risk,
            burn_rate_used=burn_rate.burn_rate_per_day,
            burn_rate_std_dev=burn_rate.burn_rate_std_dev,
            initial_quantity=product.estimated_quantity,
            confidence_score=burn_rate.confidence_score,
            skip_reason=seed["assumptions_summary"],
        )
