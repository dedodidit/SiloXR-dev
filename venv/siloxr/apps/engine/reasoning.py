# backend/apps/engine/reasoning.py
# COMPLETE replacement — remove all duplicate definitions

"""
Reasoning Engine.

Every insight reaches the user through this engine.
Transforms raw signal data into a StructuredInsight with:

  observation    — factual state (what is)
  prediction     — likely future (what will happen)
  recommendation — what to do
  impact         — cost of inaction
  context        — why this matters for this business type
  reasoning      — the evidence chain
  confidence     — 0.05–0.99

Date precision adapts to confidence.
Industry context adapts to business_type.
Impact ranges use the at-risk-days × burn-rate model.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


class DatePrecisionEngine:
    """
    Formats a future date with precision proportional to confidence.

    < 0.40  → vague   ("very soon", "within the next week")
    0.40–0.70 → approximate ("in about N days")
    > 0.70  → precise ("in ~N days (Thursday 26th)")
    """

    def format(self, days: Optional[float], confidence: float) -> str:
        if days is None:
            return "at some point"

        days_int = max(0, int(round(days)))

        if confidence < 0.40:
            if days_int <= 3:   return "very soon"
            if days_int <= 7:   return "within the next week"
            if days_int <= 14:  return "in the coming weeks"
            return "later this month"

        if confidence < 0.70:
            if days_int == 0:  return "today"
            if days_int == 1:  return "tomorrow"
            return f"in about {days_int} days"

        target    = (timezone.now() + timedelta(days=days_int)).date()
        day_name  = target.strftime("%A")
        day_num   = target.day
        return f"in ~{days_int} days ({day_name} {day_num}{self._ordinal(day_num)})"

    @staticmethod
    def _ordinal(n: int) -> str:
        if 11 <= n % 100 <= 13: return "th"
        return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


@dataclass
class StructuredInsight:
    """
    Single canonical insight structure — the only output type
    the InsightEngine produces.

    ALL fields are mandatory. Callers should not build this directly;
    always use ReasoningEngine.generate().
    """
    detector:         str
    product_id:       str
    product_sku:      str
    product_name:     str
    observation:      str    # What is happening (factual)
    prediction:       str    # What will happen if no action
    recommendation:   str    # What to do
    impact:           str    # Cost of inaction (human-readable)
    context:          str    # Business-type-aware framing
    reasoning:        str    # Evidence chain (used by gating layer)
    confidence:       float
    date_signal:      str    # DatePrecisionEngine output
    severity:         str    # critical | warning | info | ok
    action_type:      str    # Maps to DecisionLog action constants
    urgency_tier:     str    # critical | warning | info
    lost_sales_est:   float  # Numeric — used for impact range display
    is_industry_aware: bool = False


class ReasoningEngine:
    """
    Produces StructuredInsight from raw signal dicts.
    Called by every InsightEngine detector.
    """

    def __init__(self):
        self._date_engine = DatePrecisionEngine()

    def generate(
        self,
        product,
        detector:      str,
        signal:        dict,
        business_type: str = "",
    ) -> StructuredInsight:
        """
        Generate a StructuredInsight from a raw signal dict.

        Expected signal keys (all optional):
          stockout_days, demand_direction, confidence,
          burn_rate, estimated_quantity, drift_pct, pattern_type
        """
        confidence    = signal.get("confidence", 0.5)
        stockout_days = signal.get("stockout_days")
        direction     = signal.get("demand_direction", "stable")
        qty           = signal.get("estimated_quantity", product.estimated_quantity)
        burn          = signal.get("burn_rate", 0)
        drift         = signal.get("drift_pct", 0)

        date_str = self._date_engine.format(stockout_days, confidence)
        industry = self._industry_context(business_type, product)

        (obs, pred, rec, impact, ctx, rsn,
         sev, action, urgency, lost) = self._compose(
            detector, product, confidence, date_str,
            direction, qty, burn, drift, industry, signal,
        )

        return StructuredInsight(
            detector         = detector,
            product_id       = str(product.id),
            product_sku      = product.sku,
            product_name     = product.name,
            observation      = obs,
            prediction       = pred,
            recommendation   = rec,
            impact           = impact,
            context          = ctx,
            reasoning        = rsn,
            confidence       = confidence,
            date_signal      = date_str,
            severity         = sev,
            action_type      = action,
            urgency_tier     = urgency,
            lost_sales_est   = lost,
            is_industry_aware = bool(industry),
        )

    def _compose(
        self, detector, product, confidence, date_str,
        direction, qty, burn, drift, industry, signal,
    ) -> tuple:
        """
        Returns:
          (obs, pred, rec, impact, ctx, rsn, sev, action, urgency_tier, lost_sales_est)
        All 10 values — consumed directly by generate().
        """
        name       = product.name
        sku        = product.sku
        unit       = product.unit
        conf_pct   = int(confidence * 100)
        stockout_d = signal.get("stockout_days")

        at_risk_days   = min(float(stockout_d or 0), 7.0)
        lost_sales_est = round(at_risk_days * burn, 1) if burn > 0 else 0.0
        lost_sales_low = max(1, int(lost_sales_est * 0.8))
        lost_sales_hi  = max(2, int(lost_sales_est * 1.2))

        if detector == "StockRiskDetector":
            obs    = f"{name} ({sku}) has approximately {qty:.0f} {unit} remaining."
            pred   = (
                f"Stock is expected to run out {date_str}."
                if confidence >= 0.70
                else f"At the current consumption rate, stock may run out {date_str}."
            )
            rec    = (
                f"Reorder {name} now to avoid a stockout {date_str}."
                if confidence >= 0.60
                else f"Consider restocking {name} before it runs out."
            )
            impact = (
                f"If not addressed, you may miss approximately "
                f"{lost_sales_low}–{lost_sales_hi} sales of {name}."
                if lost_sales_est > 0
                else f"Leaving this unaddressed risks lost revenue on {name}."
            )
            ctx    = (
                f"{industry}Stock levels are approaching a critical point. "
                f"At {burn:.1f} {unit}/day this represents a real supply risk."
            )
            rsn    = (
                f"Based on recent sales patterns, {date_str} is the estimated "
                f"depletion point. Confidence: {conf_pct}%."
            )
            sev     = "critical" if (stockout_d or 99) <= 3 else "warning"
            action  = "ALERT_CRITICAL" if sev == "critical" else "ALERT_LOW"
            urgency = sev

        elif detector == "DemandShiftDetector":
            dir_word = {"increasing": "rising", "decreasing": "easing"}.get(direction, "stable")
            obs    = f"Demand for {name} appears to be {dir_word}."
            pred   = (
                "If this trend continues, stock may deplete faster than usual."
                if direction == "increasing"
                else "Consumption may slow over the coming days."
            )
            rec    = (
                "Consider ordering ahead of your normal schedule."
                if direction == "increasing"
                else "You may be able to reduce your next order quantity."
            )
            impact = (
                "Ordering too late could result in a stockout during peak demand."
                if direction == "increasing"
                else "Over-ordering now ties up capital in slow-moving stock."
            )
            ctx    = (
                f"{industry}Recent sales trends show a {direction} pattern. "
                f"This affects optimal stock levels."
            )
            rsn    = (
                f"Comparing the last 7 days vs the prior week shows a "
                f"{'positive' if direction == 'increasing' else 'negative'} shift. "
                f"Confidence: {conf_pct}%."
            )
            sev     = "warning" if direction != "stable" else "info"
            action  = "EXPECT_HIGH_DEMAND" if direction == "increasing" else "REDUCE_STOCK"
            urgency = "warning" if direction != "stable" else "info"

        elif detector == "PatternDetector":
            pattern = signal.get("pattern_type", "weekly")
            obs    = f"{name} shows a recurring {pattern} consumption pattern."
            pred   = (
                f"Stock requirements for {name} will likely peak on the "
                f"high-consumption days of the {pattern} cycle."
            )
            rec    = f"Time your restocks around the {pattern} peak to avoid shortfalls."
            impact = "Missing the restock window during peak demand may cause temporary stockouts."
            ctx    = f"{industry}Recognising this pattern allows more accurate ordering."
            rsn    = (
                f"Historical data shows consistent {pattern} variation with "
                f"{conf_pct}% pattern consistency."
            )
            sev     = "info"
            action  = "MONITOR"
            urgency = "info"

        elif detector == "ProfitRiskDetector":
            days_stock = qty / max(burn, 0.01)
            obs    = f"{name} has approximately {days_stock:.0f} days of stock remaining."
            pred   = (
                f"At the current rate, this stock will not be fully consumed "
                f"for over {int(days_stock)} days."
            )
            rec    = f"Consider a smaller next order for {name} to free up working capital."
            impact = (
                "Holding excess stock ties up capital that could be deployed elsewhere. "
                "Reducing the next order by 20–30% may improve cash flow."
            )
            ctx    = f"{industry}Overstocking risks spoilage, waste, and capital inefficiency."
            rsn    = (
                f"Current consumption rate ({burn:.1f}/day) suggests stock will last "
                f"longer than typical reorder cycles. Confidence: {conf_pct}%."
            )
            sev     = "info"
            action  = "DELAY_PURCHASE"
            urgency = "info"

        elif detector == "DataQualityDetector":
            obs    = f"The system has limited data on {name} ({conf_pct}% confidence)."
            pred   = (
                f"Without a recent stock count, predictions for {name} "
                f"may drift from reality over time."
            )
            rec    = (
                f"Record a stock count for {name} — even a rough count "
                f"improves forecast accuracy significantly."
            )
            impact = (
                "Without better data, the system may generate inaccurate "
                f"recommendations for {name}."
            )
            ctx    = f"{industry}Low-confidence products receive less precise intelligence."
            rsn    = f"Few recent sale events have been recorded. Current confidence: {conf_pct}%."
            sev     = "info"
            action  = "CHECK_STOCK"
            urgency = "info"

        elif detector == "AnomalyDetector":
            direction_word = "above" if drift > 0 else "below"
            obs    = (
                f"Consumption of {name} was {abs(drift):.0f}% "
                f"{direction_word} the expected rate recently."
            )
            pred   = (
                "If this rate persists, the current stock forecast may be "
                "inaccurate by a significant margin."
            )
            rec    = f"Verify whether the recent change in {name} consumption was expected."
            impact = (
                "Relying on the current forecast without verification could lead "
                "to an unexpected stockout or overstock situation."
            )
            ctx    = (
                f"{industry}An anomaly in consumption may reflect a bulk sale, "
                "a count error, or a real demand shift."
            )
            rsn    = (
                f"Recent consumption deviated {abs(drift):.0f}% from the "
                f"established burn rate. Confidence: {conf_pct}%."
            )
            sev     = "warning"
            action  = "CHECK_STOCK"
            urgency = "warning"

        elif detector == "OpportunityDetector":
            obs    = f"Demand for {name} is rising while stock is running low."
            pred   = (
                "If demand continues at this rate and stock is not replenished, "
                "you may experience a stockout during peak demand."
            )
            rec    = (
                f"Consider increasing your next order of {name} "
                "to meet anticipated demand."
            )
            impact = (
                f"Missing this demand window could mean losing "
                f"{lost_sales_low}–{lost_sales_hi} potential sales of {name}."
            )
            ctx    = (
                f"{industry}Rising demand with low stock is a high-opportunity, "
                "high-risk signal."
            )
            rsn    = (
                f"Demand direction is increasing with {conf_pct}% confidence "
                "and stock covers fewer than 20 days."
            )
            sev     = "warning"
            action  = "EXPECT_HIGH_DEMAND"
            urgency = "warning"

        else:
            obs    = f"Signal detected for {name}."
            pred   = f"Trends for {name} warrant monitoring."
            rec    = f"Review {name} at your next opportunity."
            impact = "No immediate impact estimated."
            ctx    = f"System analysis flagged {name} for review."
            rsn    = f"Confidence: {conf_pct}%."
            sev     = "info"
            action  = "MONITOR"
            urgency = "info"

        return obs, pred, rec, impact, ctx, rsn, sev, action, urgency, lost_sales_est

    def _industry_context(self, business_type: str, product) -> str:
        if not business_type:
            return ""
        ctx_map = {
            "retail":      "For a retail business, ",
            "wholesale":   "In wholesale distribution, ",
            "pharmacy":    "In a pharmacy setting, ",
            "pharma":      "In a pharmacy setting, ",
            "food":        "For food and beverage businesses, ",
            "hardware":    "For hardware and building supply, ",
            "supermarket": "In a supermarket context, ",
            "auto":        "For automotive parts, ",
        }
        for key, phrase in ctx_map.items():
            if key in business_type.lower():
                return phrase
        return "For your business type, "