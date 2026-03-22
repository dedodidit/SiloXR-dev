# backend/apps/engine/feedback.py
#
# CHANGES FROM ORIGINAL (all additive):
#
#   1. FalseAlertPenaliser — NEW class added at the bottom of the file.
#      Detects resolved snapshots where an alert was issued but the
#      forecast was significantly wrong, and applies a small confidence
#      penalty to the product. Called from FeedbackEngine.run().
#
#   2. FeedbackEngine.run() — calls FalseAlertPenaliser after the existing
#      correction signal is built. One new method call, one new log line.
#
#   3. FeedbackEngine.run_for_all_active() — unchanged.
#
#   4. No existing class, constant, dataclass, or method is changed.
#   5. No new DB fields are needed. Penalty is applied via the existing
#      Product.confidence_score field (already updated by _apply_correction).
#
# ─────────────────────────────────────────────────────────────────────────────

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Avg, Count, F, FloatField, Q
from django.db.models.functions import Abs
from django.utils import timezone

from apps.inventory.models import (
    BurnRate,
    DecisionLog,
    ForecastSnapshot,
    InventoryEvent,
    Product,
)
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Existing data structures — UNCHANGED
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ForecastError:
    snapshot_id:    str
    forecast_date:  date
    predicted:      float
    actual:         float
    error:          float
    abs_error:      float
    pct_error:      float
    over_predicted: bool


@dataclass
class ProductAccuracyReport:
    product_id:     str
    product_sku:    str
    resolved_count: int
    mae:            float
    mape:           float
    bias:           float
    bias_direction: str
    errors:         list[ForecastError] = field(default_factory=list)
    window_days:    int = 30


@dataclass
class CorrectionSignal:
    product_id:             str
    product_sku:            str
    rate_adjustment_factor: float
    suggested_window_days:  Optional[int]
    confidence_penalty:     float
    summary:                str
    actionable:             bool = True
    accuracy:               Optional[ProductAccuracyReport] = None


# ══════════════════════════════════════════════════════════════════════════════
# Existing sub-components — UNCHANGED
# ══════════════════════════════════════════════════════════════════════════════

class ActualResolver:
    """
    Resolves past ForecastSnapshots against physical counts.
    UNCHANGED from original.
    """

    RESOLUTION_WINDOW_DAYS = 3

    def resolve_pending(self, product: Product) -> list[ForecastSnapshot]:
        pending = ForecastSnapshot.objects.filter(
            product=product,
            forecast_date__lte=date.today(),
            actual_quantity__isnull=True,
        ).order_by("forecast_date")

        resolved = []
        for snapshot in pending:
            actual = self._find_actual(product, snapshot.forecast_date)
            if actual is not None:
                self._write_actual(snapshot, actual)
                resolved.append(snapshot)

        logger.debug(
            "Resolved %d / %d pending snapshots for %s",
            len(resolved), pending.count(), product.sku,
        )
        return resolved

    def _find_actual(
        self, product: Product, target_date: date
    ) -> Optional[float]:
        window_start = target_date - timedelta(days=self.RESOLUTION_WINDOW_DAYS)
        window_end   = target_date + timedelta(days=self.RESOLUTION_WINDOW_DAYS)

        count_event = (
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.STOCK_COUNT,
                occurred_at__date__range=(window_start, window_end),
                verified_quantity__isnull=False,
            )
            .first()
        )

        if count_event:
            count_events = list(
                InventoryEvent.objects.filter(
                    product=product,
                    event_type=InventoryEvent.STOCK_COUNT,
                    occurred_at__date__range=(window_start, window_end),
                    verified_quantity__isnull=False,
                )
            )
            closest = min(
                count_events,
                key=lambda e: abs((e.occurred_at.date() - target_date).days),
            )
            return float(closest.verified_quantity)

        return self._reconstruct_quantity(product, target_date)

    def _reconstruct_quantity(
        self, product: Product, target_date: date
    ) -> Optional[float]:
        anchor_event = (
            InventoryEvent.objects
            .filter(
                product=product,
                event_type=InventoryEvent.STOCK_COUNT,
                occurred_at__date__lte=target_date,
                verified_quantity__isnull=False,
            )
            .order_by("-occurred_at")
            .first()
        )

        if anchor_event is None:
            return None

        anchor_qty  = float(anchor_event.verified_quantity)
        anchor_date = anchor_event.occurred_at

        subsequent_events = InventoryEvent.objects.filter(
            product=product,
            occurred_at__gt=anchor_date,
            occurred_at__date__lte=target_date,
        ).exclude(event_type=InventoryEvent.STOCK_COUNT)

        net_delta = sum(e.signed_quantity for e in subsequent_events)
        return max(0.0, anchor_qty + net_delta)

    @transaction.atomic
    def _write_actual(
        self, snapshot: ForecastSnapshot, actual: float
    ) -> None:
        snapshot.actual_quantity = actual
        snapshot.forecast_error  = snapshot.predicted_quantity - actual
        snapshot.save(update_fields=["actual_quantity", "forecast_error"])


class ErrorCalculator:
    """UNCHANGED from original."""

    def calculate(
        self,
        product:             Product,
        resolved_snapshots:  list[ForecastSnapshot],
        window_days:         int = 30,
    ) -> Optional[ProductAccuracyReport]:
        if len(resolved_snapshots) < 3:
            logger.debug(
                "Insufficient resolved snapshots for %s (%d) — skipping error calc",
                product.sku, len(resolved_snapshots),
            )
            return None

        errors: list[ForecastError] = []

        for snap in resolved_snapshots:
            if snap.actual_quantity is None or snap.actual_quantity <= 0:
                continue

            error     = snap.predicted_quantity - snap.actual_quantity
            abs_error = abs(error)
            pct_error = (abs_error / snap.actual_quantity) * 100

            errors.append(ForecastError(
                snapshot_id=str(snap.id),
                forecast_date=snap.forecast_date,
                predicted=snap.predicted_quantity,
                actual=snap.actual_quantity,
                error=error,
                abs_error=abs_error,
                pct_error=pct_error,
                over_predicted=(error > 0),
            ))

        if not errors:
            return None

        mae  = statistics.mean(e.abs_error for e in errors)
        mape = statistics.mean(e.pct_error for e in errors)
        bias = statistics.mean(e.error     for e in errors)

        bias_direction = (
            "over"    if bias >  5 else
            "under"   if bias < -5 else
            "neutral"
        )

        return ProductAccuracyReport(
            product_id=str(product.id),
            product_sku=product.sku,
            resolved_count=len(errors),
            mae=round(mae, 3),
            mape=round(mape, 3),
            bias=round(bias, 3),
            bias_direction=bias_direction,
            errors=errors,
            window_days=window_days,
        )


class BiasDetector:
    """UNCHANGED from original."""

    MAX_ADJUSTMENT = 0.20
    MAPE_THRESHOLD = 15.0

    def compute_adjustment(self, report: ProductAccuracyReport) -> float:
        if report.mape < self.MAPE_THRESHOLD:
            return 1.0

        excess_mape    = report.mape - self.MAPE_THRESHOLD
        raw_adjustment = min(self.MAX_ADJUSTMENT, excess_mape / 100.0)

        if report.bias_direction == "over":
            return round(1.0 + raw_adjustment, 4)
        elif report.bias_direction == "under":
            return round(1.0 - raw_adjustment, 4)
        return 1.0

    def suggest_window(
        self, report: ProductAccuracyReport, current_window: int
    ) -> Optional[int]:
        if report.mape < 25.0:
            return None
        if report.bias_direction == "over" and current_window > 14:
            return max(14, current_window - 7)
        if report.bias_direction == "under" and current_window < 60:
            return min(60, current_window + 7)
        return None


class ConfidenceAuditor:
    """UNCHANGED from original."""

    ACCURACY_TOLERANCE_PCT = 20.0

    def compute_penalty(self, report: ProductAccuracyReport) -> float:
        if report.resolved_count < 3:
            return 0.0

        errors               = report.errors
        avg_confidence_used  = 0.75
        wrong_count          = sum(
            1 for e in errors if e.pct_error > self.ACCURACY_TOLERANCE_PCT
        )
        error_rate           = wrong_count / len(errors)
        stated_accuracy      = avg_confidence_used
        actual_accuracy      = 1.0 - error_rate
        calibration_gap      = max(0.0, stated_accuracy - actual_accuracy)
        return round(min(0.5, calibration_gap), 4)


# ══════════════════════════════════════════════════════════════════════════════
# NEW — False Alert Penaliser (requirement 5)
# ══════════════════════════════════════════════════════════════════════════════

class FalseAlertPenaliser:
    """
    Detects resolved snapshots that had an associated alert decision but
    a significantly inaccurate forecast, and applies a small confidence
    penalty to the product.

    Definition of a false alert:
      An ALERT_CRITICAL or ALERT_LOW was issued for a product on a date
      for which we now have a resolved ForecastSnapshot, AND the forecast
      error was above FALSE_ALERT_ERROR_THRESHOLD (default: 40%).

    This is distinct from the ConfidenceAuditor's calibration penalty:
    - ConfidenceAuditor penalises general forecast inaccuracy (MAPE drift).
    - FalseAlertPenaliser penalises specifically the cases where the system
      raised an urgent alarm that turned out to be wrong. This is the trust-
      critical case.

    Penalty design:
    - Small fixed decrement per false alert found (FALSE_ALERT_PENALTY_PER_CASE)
    - Applied directly to Product.confidence_score via .update()
    - Capped at MAX_TOTAL_PENALTY so repeated false alerts don't zeroise confidence
    - Floor: confidence will not drop below MIN_CONFIDENCE_FLOOR
    - Only fires when a minimum number of resolved cases exist (MIN_CASES)

    The penalty is intentionally conservative. The goal is a slow, honest
    correction signal — not a crash. ConfidenceScorer will recompute properly
    on the next LearningEngine run and may restore confidence if data improves.
    """

    FALSE_ALERT_ERROR_THRESHOLD  = 0.40   # 40% forecast error on an alerted day
    FALSE_ALERT_PENALTY_PER_CASE = 0.03   # 3% confidence reduction per false alert
    MAX_TOTAL_PENALTY            = 0.12   # 12% maximum total reduction per cycle
    MIN_CONFIDENCE_FLOOR         = 0.10   # never reduce below 10%
    MIN_CASES                    = 2      # need at least 2 resolved alerts to act
    ALERT_ACTIONS                = {"ALERT_CRITICAL", "ALERT_LOW"}
    LOOKBACK_DAYS                = 30     # how many days back to look for resolved alerts

    def evaluate(
        self,
        product:  Product,
        resolved: list[ForecastSnapshot],
    ) -> dict:
        """
        Check resolved snapshots for false alert cases and apply penalty.

        Returns a summary dict describing what was found and what was done.
        Returns {"false_alerts": 0, "penalty_applied": 0.0} when nothing fires.
        """
        if not resolved:
            return {"false_alerts": 0, "penalty_applied": 0.0}

        resolved_dates = {snap.forecast_date for snap in resolved}

        # Find alert decisions that coincide with these resolved snapshot dates
        cutoff = timezone.now() - timedelta(days=self.LOOKBACK_DAYS)
        alert_decisions = list(
            DecisionLog.objects.filter(
                product=product,
                action__in=self.ALERT_ACTIONS,
                created_at__gte=cutoff,
            ).values("id", "action", "created_at", "confidence_score")
        )

        if not alert_decisions:
            return {"false_alerts": 0, "penalty_applied": 0.0}

        # Build a map of snapshot date → forecast error for quick lookup
        snap_errors = {
            snap.forecast_date: (
                abs(snap.forecast_error) / max(snap.actual_quantity, 1.0)
                if snap.actual_quantity and snap.forecast_error is not None
                else None
            )
            for snap in resolved
        }

        false_alert_count = 0

        for decision in alert_decisions:
            decision_date = decision["created_at"].date()

            # Find the snapshot closest to this decision date
            matching_date = min(
                (d for d in snap_errors if d >= decision_date),
                key=lambda d: (d - decision_date).days,
                default=None,
            )
            if matching_date is None:
                continue

            pct_error = snap_errors.get(matching_date)
            if pct_error is None:
                continue

            if pct_error > self.FALSE_ALERT_ERROR_THRESHOLD:
                false_alert_count += 1
                logger.debug(
                    "False alert case for %s: action=%s date=%s error=%.0f%%",
                    product.sku,
                    decision["action"],
                    decision_date,
                    pct_error * 100,
                )

        if false_alert_count < self.MIN_CASES:
            return {"false_alerts": false_alert_count, "penalty_applied": 0.0}

        # Compute total penalty — capped to prevent instability
        raw_penalty   = false_alert_count * self.FALSE_ALERT_PENALTY_PER_CASE
        total_penalty = round(min(self.MAX_TOTAL_PENALTY, raw_penalty), 4)

        # Apply: fetch current score fresh, compute new score, update atomically
        current_score = (
            Product.objects
            .filter(pk=product.pk)
            .values_list("confidence_score", flat=True)
            .first()
        ) or 0.0

        new_score = round(
            max(self.MIN_CONFIDENCE_FLOOR, current_score - total_penalty), 4
        )

        Product.objects.filter(pk=product.pk).update(confidence_score=new_score)
        product.confidence_score = new_score   # keep in-memory object in sync

        logger.info(
            "False alert penalty applied for %s: %d case(s), "
            "confidence %.3f → %.3f (penalty=%.3f)",
            product.sku,
            false_alert_count,
            current_score,
            new_score,
            total_penalty,
        )

        return {
            "false_alerts":    false_alert_count,
            "penalty_applied": total_penalty,
            "confidence_before": current_score,
            "confidence_after":  new_score,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Main engine — CHANGED: adds FalseAlertPenaliser call inside run()
# ══════════════════════════════════════════════════════════════════════════════

class FeedbackEngine:
    """
    Runs the full feedback cycle for one or all products.

    Steps (original + new step 6):
    1. Resolve pending ForecastSnapshots
    2. Calculate forecast errors (MAE, MAPE, bias)
    3. Detect bias and compute rate adjustment
    4. Audit confidence calibration
    5. Apply correction to Learning Engine
    6. NEW: Apply false alert penalty (FalseAlertPenaliser)
    """

    def __init__(self):
        self._resolver  = ActualResolver()
        self._calc      = ErrorCalculator()
        self._bias      = BiasDetector()
        self._auditor   = ConfidenceAuditor()
        self._penaliser = FalseAlertPenaliser()    # NEW

    def run(self, product: Product) -> Optional[CorrectionSignal]:
        logger.debug("Feedback cycle started for: %s", product.sku)

        # ── Step 1: Resolve pending snapshots ────────────────────────────
        resolved = self._resolver.resolve_pending(product)

        if not resolved:
            logger.debug("No resolvable snapshots for %s", product.sku)
            return None

        # ── Step 2: Calculate errors ──────────────────────────────────────
        report = self._calc.calculate(product, resolved)

        if report is None:
            return CorrectionSignal(
                product_id=str(product.id),
                product_sku=product.sku,
                rate_adjustment_factor=1.0,
                suggested_window_days=None,
                confidence_penalty=0.0,
                summary=(
                    f"Resolved {len(resolved)} snapshot(s) for {product.sku}, "
                    f"but insufficient data for error analysis yet."
                ),
                actionable=False,
            )

        # ── Step 3: Bias detection ────────────────────────────────────────
        rate_factor      = self._bias.compute_adjustment(report)
        current_window   = self._get_current_window(product)
        suggested_window = self._bias.suggest_window(report, current_window)

        # ── Step 4: Confidence audit ──────────────────────────────────────
        confidence_penalty = self._auditor.compute_penalty(report)

        # ── Step 5: Apply correction ──────────────────────────────────────
        self._apply_correction(
            product=product,
            rate_factor=rate_factor,
            confidence_penalty=confidence_penalty,
        )

        # ── Step 6: False alert penalty (NEW) ────────────────────────────
        # Runs after _apply_correction so any rate correction is already
        # reflected in the BurnRate chain before the penalty is assessed.
        # The penalty is a separate, additive reduction to confidence_score.
        penalty_result = self._penaliser.evaluate(product, resolved)
        self._emit_trust_notification(product, resolved)

        summary = self._compose_summary(
            report, rate_factor, confidence_penalty, penalty_result
        )

        signal = CorrectionSignal(
            product_id=str(product.id),
            product_sku=product.sku,
            rate_adjustment_factor=rate_factor,
            suggested_window_days=suggested_window,
            confidence_penalty=confidence_penalty,
            summary=summary,
            actionable=True,
            accuracy=report,
        )

        logger.info(
            "Feedback complete for %s: MAE=%.2f MAPE=%.1f%% bias=%s "
            "rate_factor=%.3f conf_penalty=%.3f false_alerts=%d",
            product.sku,
            report.mae,
            report.mape,
            report.bias_direction,
            rate_factor,
            confidence_penalty,
            penalty_result.get("false_alerts", 0),
        )

        return signal

    def run_for_all_active(self) -> list[CorrectionSignal]:
        """UNCHANGED from original."""
        products = Product.objects.filter(is_active=True).select_related("owner")
        signals  = []

        for product in products:
            try:
                signal = self.run(product)
                if signal:
                    signals.append(signal)
            except Exception as exc:
                logger.error(
                    "Feedback failed for %s: %s", product.sku, exc, exc_info=True
                )

        actionable = [s for s in signals if s.actionable]
        logger.info(
            "Feedback sweep complete: %d products, %d actionable signals",
            len(signals), len(actionable),
        )
        return signals

    # ── Private helpers — UNCHANGED except _compose_summary signature ─────────

    def _get_current_window(self, product: Product) -> int:
        latest = (
            BurnRate.objects
            .filter(product=product)
            .order_by("-computed_at")
            .values_list("window_days", flat=True)
            .first()
        )
        return latest if latest else 30

    def _emit_trust_notification(
        self,
        product: Product,
        resolved: list[ForecastSnapshot],
    ) -> None:
        latest = resolved[-1] if resolved else None
        if latest is None or latest.actual_quantity in [None, 0]:
            return

        decision = (
            DecisionLog.objects
            .filter(product=product, forecast=latest)
            .order_by("-created_at")
            .first()
        )
        predicted_days = None
        actual_days = None
        if decision and decision.days_remaining_at_decision is not None:
            predicted_days = max(1, round(decision.days_remaining_at_decision))
            actual_days = max(1, (latest.forecast_date - decision.created_at.date()).days)

        actual = max(float(latest.actual_quantity or 0.0), 1.0)
        abs_pct_error = abs(float(latest.forecast_error or 0.0)) / actual
        accuracy_pct = round(max(0.0, min(100.0, (1.0 - abs_pct_error) * 100.0)), 1)

        if predicted_days is None or actual_days is None:
            body = f"We resolved a forecast for {product.name}. Accuracy: {accuracy_pct:.0f}%."
        else:
            body = (
                f"Last time we predicted {product.name} would run out in about {predicted_days} day(s). "
                f"It resolved in {actual_days} day(s). Accuracy: {accuracy_pct:.0f}%."
            )

        title = f"Forecast verified: {product.name}"
        if Notification.objects.filter(user=product.owner, title=title, body=body).exists():
            return

        Notification.objects.create(
            user=product.owner,
            decision=decision,
            channel=Notification.CHANNEL_IN_APP,
            title=title,
            body=body,
            confidence=max(0.1, min(1.0, accuracy_pct / 100.0)),
        )

    @transaction.atomic
    def _apply_correction(
        self,
        product:            Product,
        rate_factor:        float,
        confidence_penalty: float,
    ) -> None:
        if rate_factor == 1.0 and confidence_penalty == 0.0:
            return

        if confidence_penalty > 0:
            current   = product.confidence_score
            penalised = max(0.1, current * (1.0 - confidence_penalty))
            Product.objects.filter(pk=product.pk).update(
                confidence_score=round(penalised, 4)
            )
            product.confidence_score = round(penalised, 4)

        if rate_factor != 1.0:
            latest_burn = (
                BurnRate.objects
                .filter(product=product)
                .order_by("-computed_at")
                .first()
            )
            if latest_burn:
                adjusted_rate = round(
                    latest_burn.burn_rate_per_day * rate_factor, 4
                )
                BurnRate.objects.create(
                    product=product,
                    burn_rate_per_day=adjusted_rate,
                    burn_rate_std_dev=latest_burn.burn_rate_std_dev,
                    confidence_score=max(
                        0.1,
                        latest_burn.confidence_score - confidence_penalty
                    ),
                    sample_days=latest_burn.sample_days,
                    sample_event_count=latest_burn.sample_event_count,
                    window_days=latest_burn.window_days,
                )

    @staticmethod
    def _compose_summary(
        report:           ProductAccuracyReport,
        rate_factor:      float,
        confidence_penalty: float,
        penalty_result:   dict,           # NEW parameter — has default-safe dict
    ) -> str:
        parts = [
            f"Evaluated {report.resolved_count} resolved forecast(s) for "
            f"{report.product_sku}.",
            f"MAE={report.mae:.1f} units, MAPE={report.mape:.1f}%, "
            f"bias={report.bias_direction} ({report.bias:+.1f} units avg).",
        ]
        if rate_factor != 1.0:
            direction = "increased" if rate_factor > 1.0 else "decreased"
            pct       = abs(rate_factor - 1.0) * 100
            parts.append(
                f"Burn rate {direction} by {pct:.1f}% to correct "
                f"{'over' if rate_factor > 1.0 else 'under'}-prediction bias."
            )
        if confidence_penalty > 0:
            parts.append(
                f"Confidence penalised by {confidence_penalty * 100:.0f}% "
                f"due to calibration drift."
            )
        false_alerts = penalty_result.get("false_alerts", 0)
        if false_alerts > 0:
            fa_penalty = penalty_result.get("penalty_applied", 0.0)
            parts.append(
                f"{false_alerts} false alert case(s) detected. "
                f"Additional confidence reduction: {fa_penalty * 100:.1f}%."
            )
        if rate_factor == 1.0 and confidence_penalty == 0.0 and false_alerts == 0:
            parts.append(
                "Forecast accuracy is within acceptable range. No correction applied."
            )
        return " ".join(parts)
