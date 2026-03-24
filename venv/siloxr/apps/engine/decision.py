# backend/apps/engine/decision.py
#
# CHANGES FROM ORIGINAL (all additive):
#
#   1. DecisionEngine.__init__  — adds self._gate = DecisionConfidenceGate()
#
#   2. DecisionEngine.run()     — inserts gate evaluation between
#                                 ActionSelector.select() and
#                                 _persist_decision(). Three new lines total.
#
#   3. _persist_decision()      — accepts two new keyword arguments:
#                                 trust_gate_note and original_action.
#                                 Both are written to the new additive
#                                 DecisionLog fields (migration required).
#
#   4. No existing class, constant, or method is removed or renamed.
#   5. THRESHOLD_MATRIX is unchanged.
#   6. All existing call sites still work — new parameters have defaults.
#
# ─────────────────────────────────────────────────────────────────────────────

import logging
import math
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.inventory.models import DecisionLog, ForecastSnapshot, Product
from apps.engine.forecast import ForecastResult
from apps.engine.feedback import ErrorCalculator
from apps.engine.confidence import ConfidenceScorer
from apps.core.statistics import compute_cv, expected_shortage, get_distribution_params

# NEW import — trust module lives in the same package
from apps.engine.trust import DecisionConfidenceGate, get_confidence_phrase

logger = logging.getLogger(__name__)


# ── Threshold matrix ───────────────────────────────────────────────────────────
# UNCHANGED — do not modify

THRESHOLD_MATRIX = [
    {
        "action":                DecisionLog.ALERT_CRITICAL,
        "min_risk":              0.80,
        "max_days_pessimistic":  3,
        "min_confidence":        0.30,
        "cooldown_hours":        6,
    },
    {
        "action":                DecisionLog.ALERT_LOW,
        "min_risk":              0.55,
        "max_days_pessimistic":  7,
        "min_confidence":        0.35,
        "cooldown_hours":        12,
    },
    {
        "action":                DecisionLog.REORDER,
        "min_risk":              0.35,
        "max_days_pessimistic":  14,
        "min_confidence":        0.45,
        "cooldown_hours":        24,
    },
    {
        "action":                DecisionLog.CHECK_STOCK,
        "min_risk":              0.10,
        "max_days_pessimistic":  None,
        "min_confidence":        0.0,
        "cooldown_hours":        48,
    },
    {
        "action":                DecisionLog.MONITOR,
        "min_risk":              0.05,
        "max_days_pessimistic":  None,
        "min_confidence":        0.40,
        "cooldown_hours":        24,
    },
]

ACTION_TTL_HOURS = {
    DecisionLog.ALERT_CRITICAL: 6,
    DecisionLog.ALERT_LOW:      12,
    DecisionLog.REORDER:        24,
    DecisionLog.CHECK_STOCK:    48,
    DecisionLog.MONITOR:        24,
    DecisionLog.HOLD:           48,
}

LOW_CONFIDENCE_FLOOR = 0.25
DECISION_CONFIDENCE_DOWNGRADE = 0.45
MIN_FINANCIAL_IMPACT_THRESHOLD = 1500.0


# ── Data structures ─────────────────────────────────────────────────────────────
# UNCHANGED

@dataclass(frozen=True)
class DecisionContext:
    product: Product
    forecast: ForecastResult
    stockout_risk: float
    days_until_stockout: Optional[float]
    days_until_stockout_pessimistic: Optional[float]
    days_until_reorder_point: Optional[float]
    confidence_score: float
    estimated_quantity: float
    reorder_point: float
    latest_snapshot: Optional[ForecastSnapshot]


@dataclass
class DecisionOutput:
    product_id: str
    product_sku: str
    action: str
    reasoning: str
    confidence_score: float
    severity: str
    days_until_stockout: Optional[float]
    days_until_stockout_pessimistic: Optional[float]
    suggested_reorder_date: Optional[object]
    estimated_quantity: float
    estimated_lost_sales: float = 0.0
    estimated_revenue_loss: float = 0.0
    risk_score: float = 0.0
    priority_score: float = 0.0
    skipped: bool = False
    skip_reason: str = ""
    decision_log_id: Optional[str] = None
    # NEW — populated when the gate fires, empty otherwise
    trust_gate_note: str = ""
    original_action: str = ""
    data_stale: bool = False
    confidence_phrase: str = ""


@dataclass(frozen=True)
class SimulationScenario:
    label: str
    delay_days: int
    projected_stock: float
    projected_stockout_date: Optional[object]
    estimated_revenue_loss: float
    confidence: float


@dataclass(frozen=True)
class DecisionSimulationResult:
    available: bool
    recommended: Optional[SimulationScenario] = None
    alternatives: list[SimulationScenario] = field(default_factory=list)
    reason: str = ""


# ── Sub-components ──────────────────────────────────────────────────────────────
# ALL UNCHANGED

class ActionSelector:
    """
    Evaluates the threshold matrix against the DecisionContext.
    UNCHANGED from original.
    """

    def select(self, ctx: DecisionContext) -> tuple[str, float]:
        if ctx.confidence_score < LOW_CONFIDENCE_FLOOR:
            return DecisionLog.CHECK_STOCK, ctx.confidence_score

        for rule in THRESHOLD_MATRIX:
            action = rule["action"]

            if ctx.stockout_risk < rule["min_risk"]:
                continue

            max_days = rule.get("max_days_pessimistic")
            if max_days is not None:
                days_pess = ctx.days_until_stockout_pessimistic
                if days_pess is None or days_pess > max_days:
                    continue

            if ctx.confidence_score < rule["min_confidence"]:
                continue

            if self._is_on_cooldown(ctx.product, action, rule["cooldown_hours"]):
                logger.debug(
                    "Action %s suppressed by cooldown for %s",
                    action, ctx.product.sku,
                )
                continue

            signal_clarity = min(
                1.0,
                (ctx.stockout_risk - rule["min_risk"]) /
                max(0.01, 1.0 - rule["min_risk"])
            )
            adjusted = (ctx.confidence_score * 0.7) + (signal_clarity * 0.3)
            return action, round(min(0.99, adjusted), 4)

        return DecisionLog.HOLD, round(ctx.confidence_score, 4)

    def _is_on_cooldown(
        self, product: Product, action: str, cooldown_hours: int
    ) -> bool:
        cutoff = timezone.now() - timedelta(hours=cooldown_hours)
        return DecisionLog.objects.filter(
            product=product,
            action=action,
            created_at__gte=cutoff,
        ).exclude(
            status=DecisionLog.STATUS_IGNORED
        ).filter(
            is_acknowledged=False
        ).exists()


class ReasoningComposer:
    """
    Produces human-readable reasoning text.
    UNCHANGED from original — get_confidence_phrase() is available
    as an import for future use but not required here.
    """

    def _language(self, confidence: float) -> str:
        if confidence >= 0.75:
            return "expected to"
        if confidence >= 0.45:
            return "likely to"
        return "may"

    def compose(self, action: str, ctx: DecisionContext, confidence: float) -> str:
        conf_pct = int(confidence * 100)
        qty = ctx.estimated_quantity
        sku = ctx.product.sku
        phrasing = self._language(confidence)

        days_central = ctx.days_until_stockout
        days_pess    = ctx.days_until_stockout_pessimistic
        days_reorder = ctx.days_until_reorder_point

        if action == DecisionLog.ALERT_CRITICAL:
            days_str = f"~{days_pess:.0f}" if days_pess else "fewer than 3"
            return (
                f"Stock for {sku} {phrasing} run critically low soon. "
                f"The pessimistic forecast suggests a potential stockout in "
                f"{days_str} days, with {qty:.0f} units currently estimated. "
                f"Consider urgent replenishment. Confidence: {conf_pct}%."
            )

        if action == DecisionLog.ALERT_LOW:
            days_str    = f"~{days_pess:.0f}" if days_pess else "~7"
            central_str = (
                f" (~{days_central:.0f} days on the central path)"
                if days_central else ""
            )
            return (
                f"Stock levels for {sku} {phrasing} run low soon. "
                f"A stockout is possible within {days_str} days{central_str}, "
                f"based on current consumption trends. "
                f"Confidence: {conf_pct}%."
            )

        if action == DecisionLog.REORDER:
            if days_reorder:
                reorder_str = (
                    f"The reorder point may be reached in ~{days_reorder:.0f} days."
                )
            else:
                reorder_str = "Stock is approaching reorder levels."
            reorder_date = ctx.forecast.suggested_reorder_date
            date_str = (
                f" Consider placing an order around {reorder_date.strftime('%b %d')}."
                if reorder_date else ""
            )
            return (
                f"{reorder_str}{date_str} "
                f"Current estimated stock: {qty:.0f} units. "
                f"Confidence: {conf_pct}%."
            )

        if action == DecisionLog.CHECK_STOCK:
            if ctx.confidence_score < LOW_CONFIDENCE_FLOOR:
                reason = (
                    f"The system's confidence in current stock levels is low "
                    f"({conf_pct}%), likely due to infrequent stock counts or "
                    f"irregular sales patterns."
                )
            else:
                reason = (
                    f"Stock levels for {sku} have not been physically verified recently. "
                    f"The estimated quantity ({qty:.0f} units) may not reflect reality."
                )
            return (
                f"{reason} "
                f"A physical stock count is suggested to restore confidence."
            )

        if action == DecisionLog.MONITOR:
            risk_pct = int(ctx.stockout_risk * 100)
            return (
                f"Stock levels for {sku} appear adequate for now, "
                f"but consumption trends suggest monitoring is warranted "
                f"(stockout risk: {risk_pct}%). "
                f"No immediate action needed. Confidence: {conf_pct}%."
            )

        # HOLD
        return (
            f"Stock levels for {sku} appear healthy with {qty:.0f} units estimated. "
            f"No action appears necessary at this time. "
            f"Confidence: {conf_pct}%."
        )


class ImpactEstimator:
    """UNCHANGED from original."""

    MIN_HORIZON_DAYS = 1.0
    MAX_HORIZON_DAYS = 14.0
    MIN_SIGMA = 0.25
    MIN_CONFIDENCE_MULTIPLIER = 0.35

    def estimate_for_window(
        self,
        ctx: DecisionContext,
        *,
        stock_on_hand: float,
        horizon_days: float,
        confidence_score: Optional[float] = None,
    ) -> tuple[float, float]:
        daily_burn = max(float(ctx.forecast.burn_rate_used or 0.0), 0.0)
        burn_sigma = max(float(ctx.forecast.burn_rate_std_dev or 0.0), 0.0)

        if daily_burn <= 0 or horizon_days <= 0:
            return 0.0, 0.0

        bounded_horizon = max(
            self.MIN_HORIZON_DAYS,
            min(float(horizon_days), self.MAX_HORIZON_DAYS),
        )
        cv = compute_cv(daily_burn, burn_sigma)
        mean_rate, adj_std = get_distribution_params(daily_burn, burn_sigma, cv)
        mu = mean_rate * bounded_horizon
        sigma = max(self.MIN_SIGMA, adj_std * math.sqrt(bounded_horizon))
        shortage = expected_shortage(mu, sigma, max(float(stock_on_hand or 0.0), 0.0))
        confidence_multiplier = max(
            self.MIN_CONFIDENCE_MULTIPLIER,
            min(1.0, float(confidence_score if confidence_score is not None else ctx.confidence_score or 0.0)),
        )
        lost_sales = round(shortage * confidence_multiplier, 2)
        selling_price = getattr(ctx.product, "selling_price", None)
        cost_price = getattr(ctx.product, "cost_price", None)

        if selling_price is None:
            return lost_sales, 0.0
        unit_margin = float(selling_price)
        if cost_price is not None:
            unit_margin = max(0.0, float(selling_price) - float(cost_price))
        return lost_sales, round(unit_margin * lost_sales, 2)

    def estimate(self, ctx: DecisionContext) -> tuple[float, float]:
        raw_horizon = (
            ctx.days_until_reorder_point
            or ctx.days_until_stockout_pessimistic
            or ctx.days_until_stockout
            or self.MIN_HORIZON_DAYS
        )
        return self.estimate_for_window(
            ctx,
            stock_on_hand=max(float(ctx.estimated_quantity or 0.0), 0.0),
            horizon_days=float(raw_horizon),
        )


class PriorityScorer:
    """UNCHANGED from original."""

    def score(
        self,
        action: str,
        ctx: DecisionContext,
        confidence: float,
        estimated_revenue_loss: float,
    ) -> tuple[float, float]:
        risk         = max(0.0, min(1.0, ctx.stockout_risk))
        if action == DecisionLog.HOLD or estimated_revenue_loss <= 0:
            return risk, 0.0

        # Revenue is normalized into a 0..1 signal so the portfolio can compare
        # products without letting a single high-price SKU dominate everything.
        revenue_factor = min(1.0, max(0.0, float(estimated_revenue_loss or 0.0) / 50000.0))
        priority = round(
            (revenue_factor * 0.60)
            + (risk * 0.25)
            + ((1.0 - max(0.0, min(1.0, confidence))) * 0.15),
            4,
        )
        return risk, priority


# ── Main engine ─────────────────────────────────────────────────────────────────

class DecisionEngine:
    """
    Reads a ForecastResult, evaluates the threshold matrix, applies the
    confidence gate, composes reasoning, and persists a DecisionLog.

    CHANGED: __init__ adds self._gate; run() calls it between select() and persist().
    All other behaviour is identical to the original.
    """

    def __init__(self):
        self._selector = ActionSelector()
        self._composer = ReasoningComposer()
        self._impact   = ImpactEstimator()
        self._priority = PriorityScorer()
        self._gate     = DecisionConfidenceGate()    # ← NEW
        self._confidence = ConfidenceScorer()
        self._errors = ErrorCalculator()

    def _sales_reliability_score(self, product: Product, forecast: ForecastResult) -> float:
        sale_events = product.events.filter(event_type=product.events.model.SALE).count()
        sample_strength = min(1.0, sale_events / 20.0)
        return round(
            max(0.1, min(1.0, (forecast.confidence_score * 0.6) + (sample_strength * 0.4))),
            4,
        )

    def _inventory_reliability_score(self, product: Product) -> float:
        recency_score = 0.2
        if product.last_verified_at:
            age_days = max(0.0, (timezone.now() - product.last_verified_at).total_seconds() / 86400.0)
            if age_days <= 2:
                recency_score = 1.0
            elif age_days <= 7:
                recency_score = 0.65
            else:
                recency_score = 0.35

        baseline_qty = max(
            float(product.last_verified_quantity or 0),
            float(product.estimated_quantity or 0),
            1.0,
        )
        gap_penalty = min(1.0, float(product.quantity_gap or 0.0) / baseline_qty)
        return round(
            max(
                0.1,
                min(
                    1.0,
                    (product.confidence_score * 0.55)
                    + (recency_score * 0.30)
                    + ((1.0 - gap_penalty) * 0.15),
                ),
            ),
            4,
        )

    def _blended_confidence(self, ctx: DecisionContext) -> float:
        srs = self._sales_reliability_score(ctx.product, ctx.forecast)
        irs = self._inventory_reliability_score(ctx.product)
        maturity = max(0.3, min(1.0, ctx.product.data_maturity_score / 100.0))
        resolved = list(
            ForecastSnapshot.objects.filter(
                product=ctx.product,
                actual_quantity__isnull=False,
            ).order_by("-forecast_date")[:30]
        )
        report = self._errors.calculate(ctx.product, resolved, window_days=30) if resolved else None
        latest_sale = ctx.product.events.filter(
            event_type=ctx.product.events.model.SALE,
        ).order_by("-occurred_at").first()
        burn_rate_obj = ctx.latest_snapshot.burn_rate if ctx.latest_snapshot and ctx.latest_snapshot.burn_rate else None
        quality = self._confidence.compute(
            last_event_date=latest_sale.occurred_at if latest_sale else None,
            sample_event_count=int(getattr(burn_rate_obj, "sample_event_count", 0) or 0),
            burn_rate_std_dev=float(ctx.forecast.burn_rate_std_dev or 0.0),
            burn_rate_per_day=float(ctx.forecast.burn_rate_used or 0.0),
            mape=(report.mape / 100.0) if report else None,
            resolved_forecasts=report.resolved_count if report else 0,
        )
        blended = quality.final_score * ((srs * 0.45) + (irs * 0.35) + (maturity * 0.20))
        return round(max(0.1, min(0.99, blended)), 4)

    def _data_stale(self, product: Product) -> bool:
        latest_event = product.events.order_by("-occurred_at").first()
        if latest_event is None:
            return True
        age_days = max(0.0, (timezone.now() - latest_event.occurred_at).total_seconds() / 86400.0)
        return age_days > self._confidence.STALE_DATA_THRESHOLD_DAYS

    def _assumption_message(self, ctx: DecisionContext) -> str:
        burn_rate = ctx.latest_snapshot.burn_rate if ctx.latest_snapshot and ctx.latest_snapshot.burn_rate else None
        if burn_rate and int(getattr(burn_rate, "sample_event_count", 0) or 0) == 0:
            return "Using baseline assumptions due to limited data"
        return ""

    def simulation_available(self, decision: DecisionLog) -> bool:
        revenue_loss = float(decision.estimated_revenue_loss or 0.0)
        confidence = float(decision.confidence_score or 0.0)
        return revenue_loss > MIN_FINANCIAL_IMPACT_THRESHOLD and 0.5 <= confidence <= 0.8

    def _build_context_for_decision(self, product: Product, decision: DecisionLog) -> DecisionContext:
        forecast_snapshot = decision.forecast
        burn_rate = float(decision.burn_rate_at_decision or 0.0)
        burn_sigma = 0.0
        forecast_confidence = float(decision.confidence_score or product.confidence_score or 0.5)

        if forecast_snapshot and forecast_snapshot.burn_rate:
            burn_sigma = float(forecast_snapshot.burn_rate.burn_rate_std_dev or 0.0)
            forecast_confidence = float(forecast_snapshot.confidence_score or forecast_confidence)

        forecast = ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=14,
            days_until_stockout=decision.days_remaining_at_decision,
            days_until_stockout_pessimistic=decision.days_remaining_at_decision,
            days_until_reorder_point=decision.days_remaining_at_decision,
            suggested_reorder_date=None,
            stockout_risk_score=float(decision.risk_score or 0.0),
            burn_rate_used=burn_rate,
            burn_rate_std_dev=burn_sigma,
            initial_quantity=float(decision.estimated_quantity_at_decision or product.estimated_quantity or 0.0),
            confidence_score=forecast_confidence,
        )
        return DecisionContext(
            product=product,
            forecast=forecast,
            stockout_risk=float(decision.risk_score or 0.0),
            days_until_stockout=decision.days_remaining_at_decision,
            days_until_stockout_pessimistic=decision.days_remaining_at_decision,
            days_until_reorder_point=decision.days_remaining_at_decision,
            confidence_score=float(decision.confidence_score or 0.0),
            estimated_quantity=float(product.estimated_quantity or decision.estimated_quantity_at_decision or 0.0),
            reorder_point=float(product.reorder_point or 0.0),
            latest_snapshot=forecast_snapshot,
        )

    def _simulation_action_label(self, action: str, delay_days: int) -> str:
        if action in {DecisionLog.REORDER, DecisionLog.ALERT_CRITICAL, DecisionLog.ALERT_LOW}:
            if delay_days <= 0:
                return "Restock today"
            if delay_days >= 3:
                return "Do nothing"
            return f"Wait {delay_days} day{'s' if delay_days != 1 else ''}"
        if action == DecisionLog.CHECK_STOCK:
            if delay_days <= 0:
                return "Check stock today"
            if delay_days >= 3:
                return "Do nothing"
            return f"Wait {delay_days} day{'s' if delay_days != 1 else ''}"
        if delay_days >= 3:
            return "Do nothing"
        return "Act today" if delay_days <= 0 else f"Wait {delay_days} day{'s' if delay_days != 1 else ''}"

    def _simulate_scenario(
        self,
        ctx: DecisionContext,
        decision: DecisionLog,
        *,
        delay_days: int,
        replenish: bool,
        label: str,
    ) -> SimulationScenario:
        daily_burn = max(float(ctx.forecast.burn_rate_used or 0.0), 0.0)
        starting_stock = max(float(ctx.estimated_quantity or 0.0), 0.0)
        analysis_horizon = max(
            self._impact.MIN_HORIZON_DAYS,
            min(
                float(
                    ctx.days_until_reorder_point
                    or ctx.days_until_stockout_pessimistic
                    or ctx.days_until_stockout
                    or 3.0
                ),
                self._impact.MAX_HORIZON_DAYS,
            ),
        )

        suggested_restock = max(
            int(getattr(ctx.product, "reorder_quantity", 0) or 0),
            int(getattr(ctx.product, "reorder_point", 0) or 0),
            int(math.ceil(daily_burn * max(3.0, analysis_horizon))),
            1,
        )

        lost_sales_before, revenue_before = (0.0, 0.0)
        stock_after_delay = starting_stock
        if delay_days > 0 and daily_burn > 0:
            lost_sales_before, revenue_before = self._impact.estimate_for_window(
                ctx,
                stock_on_hand=starting_stock,
                horizon_days=delay_days,
                confidence_score=decision.confidence_score,
            )
            stock_after_delay = max(0.0, starting_stock - (daily_burn * delay_days))

        projected_stock = stock_after_delay + (suggested_restock if replenish else 0.0)
        remaining_horizon = max(self._impact.MIN_HORIZON_DAYS, analysis_horizon - delay_days)
        lost_sales_after, revenue_after = self._impact.estimate_for_window(
            ctx,
            stock_on_hand=projected_stock,
            horizon_days=remaining_horizon,
            confidence_score=decision.confidence_score,
        )

        projected_stockout_days = None
        projected_stockout_date = None
        if daily_burn > 0:
            projected_stockout_days = max(0.0, projected_stock / daily_burn)
            projected_stockout_date = timezone.now().date() + timedelta(days=int(math.ceil(projected_stockout_days)))

        return SimulationScenario(
            label=label,
            delay_days=delay_days,
            projected_stock=round(projected_stock, 2),
            projected_stockout_date=projected_stockout_date,
            estimated_revenue_loss=round(revenue_before + revenue_after, 2),
            confidence=round(float(decision.confidence_score or 0.0), 4),
        )

    def simulate_decision_scenarios(self, product: Product, decision: DecisionLog) -> DecisionSimulationResult:
        if not self.simulation_available(decision):
            return DecisionSimulationResult(
                available=False,
                reason="Simulation is only shown for medium-confidence decisions with meaningful financial impact.",
            )

        ctx = self._build_context_for_decision(product, decision)
        short_delay = 1 if (decision.days_remaining_at_decision or 99) <= 2 else 2
        no_action_delay = max(
            3,
            int(math.ceil(decision.days_remaining_at_decision or ctx.days_until_stockout_pessimistic or 3)),
        )
        replenishable = decision.action in {
            DecisionLog.REORDER,
            DecisionLog.ALERT_CRITICAL,
            DecisionLog.ALERT_LOW,
        }

        recommended = self._simulate_scenario(
            ctx,
            decision,
            delay_days=0,
            replenish=replenishable,
            label=self._simulation_action_label(decision.action, 0),
        )
        short_wait = self._simulate_scenario(
            ctx,
            decision,
            delay_days=short_delay,
            replenish=replenishable,
            label=self._simulation_action_label(decision.action, short_delay),
        )
        no_action = self._simulate_scenario(
            ctx,
            decision,
            delay_days=no_action_delay,
            replenish=False,
            label="Do nothing",
        )

        return DecisionSimulationResult(
            available=True,
            recommended=recommended,
            alternatives=[short_wait, no_action],
        )

    def run(
        self,
        product:  Product,
        forecast: ForecastResult,
    ) -> DecisionOutput:
        logger.debug("Decision cycle for %s", product.sku)

        if forecast.skipped:
            return DecisionOutput(
                product_id=str(product.id),
                product_sku=product.sku,
                action=DecisionLog.CHECK_STOCK,
                reasoning=(
                    f"Unable to produce a forecast for {product.sku}: "
                    f"{forecast.skip_reason} A stock count is suggested."
                ),
                confidence_score=0.1,
                severity="info",
                days_until_stockout=None,
                days_until_stockout_pessimistic=None,
                suggested_reorder_date=None,
                estimated_quantity=product.estimated_quantity,
                skipped=True,
                skip_reason=f"Forecast skipped: {forecast.skip_reason}",
            )

        # ── Assemble context ─────────────────────────────────────────────
        latest_snapshot = (
            ForecastSnapshot.objects
            .filter(product=product)
            .order_by("forecast_date")
            .first()
        )

        ctx = DecisionContext(
            product=product,
            forecast=forecast,
            stockout_risk=forecast.stockout_risk_score,
            days_until_stockout=forecast.days_until_stockout,
            days_until_stockout_pessimistic=forecast.days_until_stockout_pessimistic,
            days_until_reorder_point=forecast.days_until_reorder_point,
            confidence_score=forecast.confidence_score,
            estimated_quantity=product.estimated_quantity,
            reorder_point=float(product.reorder_point),
            latest_snapshot=latest_snapshot,
        )
        ctx = replace(ctx, confidence_score=self._blended_confidence(ctx))

        # ── Select action (threshold matrix — unchanged) ──────────────────
        action, confidence = self._selector.select(ctx)

        # ── Apply confidence gate ─────────────────────────────────────────
        # NEW BLOCK — 4 lines. Does not touch any existing variable before it.
        gate_result = self._gate.evaluate(action, confidence, ctx)
        action      = gate_result.final_action
        confidence  = gate_result.final_confidence
        # ── End new block ─────────────────────────────────────────────────

        # ── Score, impact, reasoning ──────────────────────────────────────
        estimated_lost_sales, estimated_revenue_loss = self._impact.estimate(ctx)
        if confidence < DECISION_CONFIDENCE_DOWNGRADE and action != DecisionLog.CHECK_STOCK:
            action = DecisionLog.CHECK_STOCK

        if (
            action in {DecisionLog.ALERT_CRITICAL, DecisionLog.ALERT_LOW, DecisionLog.REORDER, DecisionLog.MONITOR}
            and estimated_revenue_loss < MIN_FINANCIAL_IMPACT_THRESHOLD
        ):
            action = DecisionLog.HOLD

        risk_score, priority_score = self._priority.score(
            action,
            ctx,
            confidence,
            estimated_revenue_loss,
        )
        reasoning = self._composer.compose(action, ctx, confidence)
        assumption_message = self._assumption_message(ctx)
        if assumption_message:
            reasoning = f"{reasoning} {assumption_message}."

        # Append gate note to reasoning when the gate fired so the user
        # sees a plain-language explanation of why the action was softened.
        if gate_result.was_gated:
            reasoning = f"{reasoning} Note: {gate_result.gate_note}"

        # ── Persist ───────────────────────────────────────────────────────
        log = self._persist_decision(
            product,
            forecast,
            ctx,
            action,
            reasoning,
            confidence,
            estimated_lost_sales,
            estimated_revenue_loss,
            risk_score,
            priority_score,
            trust_gate_note=gate_result.gate_note,           # NEW kwarg
            original_action=gate_result.original_action,    # NEW kwarg
        )

        output = DecisionOutput(
            product_id=str(product.id),
            product_sku=product.sku,
            action=action,
            reasoning=reasoning,
            confidence_score=confidence,
            severity=DecisionLog.ACTION_SEVERITY.get(action, "info"),
            days_until_stockout=forecast.days_until_stockout,
            days_until_stockout_pessimistic=forecast.days_until_stockout_pessimistic,
            suggested_reorder_date=forecast.suggested_reorder_date,
            estimated_quantity=product.estimated_quantity,
            estimated_lost_sales=estimated_lost_sales,
            estimated_revenue_loss=estimated_revenue_loss,
            risk_score=risk_score,
            priority_score=priority_score,
            decision_log_id=str(log.id),
            trust_gate_note=gate_result.gate_note,           # NEW field
            original_action=gate_result.original_action,    # NEW field
            data_stale=self._data_stale(product),
            confidence_phrase=get_confidence_phrase(confidence),
        )

        logger.info(
            "Decision for %s: %s (conf=%.0f%%, severity=%s%s)",
            product.sku, action,
            confidence * 100,
            output.severity,
            f", gated from {gate_result.original_action}" if gate_result.was_gated else "",
        )

        return output

    def run_for_all_pro_products(self) -> list[DecisionOutput]:
        """UNCHANGED from original."""
        from apps.engine.forecast import ForecastEngine

        products = (
            Product.objects
            .filter(is_active=True, owner__tier__in=["core", "pro", "enterprise"])
            .select_related("owner")
        )

        forecast_engine = ForecastEngine()
        outputs         = []

        for product in products:
            try:
                forecast = forecast_engine.run(product)
                output   = self.run(product, forecast)
                outputs.append(output)
            except Exception as exc:
                logger.error(
                    "Decision failed for %s: %s", product.sku, exc, exc_info=True
                )

        return outputs

    # ── Private helpers ───────────────────────────────────────────────────────

    @transaction.atomic
    def _persist_decision(
        self,
        product:               Product,
        forecast:              ForecastResult,
        ctx:                   DecisionContext,
        action:                str,
        reasoning:             str,
        confidence:            float,
        estimated_lost_sales:  float,
        estimated_revenue_loss: float,
        risk_score:            float,
        priority_score:        float,
        trust_gate_note:       str = "",    # NEW — default keeps old call sites working
        original_action:       str = "",    # NEW — default keeps old call sites working
    ) -> DecisionLog:
        ttl_hours      = ACTION_TTL_HOURS.get(action, 24)
        expires_at     = timezone.now() + timedelta(hours=ttl_hours)
        latest_snapshot = ctx.latest_snapshot

        return DecisionLog.objects.create(
            product=product,
            forecast=latest_snapshot,
            action=action,
            reasoning=reasoning,
            confidence_score=round(confidence, 4),
            estimated_quantity_at_decision=product.estimated_quantity,
            days_remaining_at_decision=forecast.days_until_stockout,
            burn_rate_at_decision=forecast.burn_rate_used,
            estimated_lost_sales=estimated_lost_sales,
            estimated_revenue_loss=estimated_revenue_loss,
            risk_score=risk_score,
            priority_score=priority_score,
            expires_at=expires_at,
            # NEW additive fields — will be empty string if gate did not fire
            trust_gate_note=trust_gate_note,
            original_action=original_action,
        )
