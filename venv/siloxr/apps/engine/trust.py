# backend/apps/engine/trust.py

"""
Decision Confidence Gate.

A pure evaluation layer that sits between the ActionSelector's raw output
and the final DecisionLog write. It answers one question:

    "Is the evidence strong enough to justify this action,
     or would showing it damage user trust more than help it?"

Design principles
─────────────────
1. The threshold matrix in decision.py is NOT changed.
   All existing logic runs first. This layer only post-processes the result.

2. Every suppression is explainable.
   GateResult carries a reason string that is appended to DecisionLog.reasoning
   and stored in DecisionLog.trust_gate_note (new additive field).
   Users see honest language. Developers see the full technical reason.

3. Downgrade, never silently drop.
   No action is silently discarded. Every suppression produces a substitute
   action (CHECK_STOCK or MONITOR) so the product still appears in the
   dashboard — just with lower urgency.

4. The gate is bypassed for safe actions.
   HOLD, CHECK_STOCK, and MONITOR pass through unchanged. The gate only
   operates on actions that could cause a false alarm.

5. Ordered filters, first match wins.
   Filters run in priority order. Once one triggers, remaining filters
   are skipped. This prevents double-penalty and produces a single,
   clean reason string.

Integration point
─────────────────
Called inside DecisionEngine.run() immediately after ActionSelector.select():

    action, confidence = self._selector.select(ctx)
    gate_result = DecisionConfidenceGate().evaluate(action, confidence, ctx)
    action     = gate_result.final_action
    confidence = gate_result.final_confidence

The gate result is also threaded into _persist_decision() so the note
is stored on the DecisionLog record.

Additive schema change required
────────────────────────────────
Add two nullable fields to DecisionLog (migration is additive, safe):

    trust_gate_note   = TextField(blank=True, default="")
    original_action   = CharField(max_length=30, blank=True, default="")

These are never read by existing serializers and do not affect any API.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Confidence language helper (requirement 6)
# ══════════════════════════════════════════════════════════════════════════════

def get_confidence_phrase(confidence: float) -> str:
    """
    Returns a hedge word calibrated to the confidence score.

    Used by ReasoningComposer and any template that needs to express
    uncertainty in natural language.

        < 0.40  → "might"
        0.40–0.70 → "likely"
        > 0.70  → "expected"

    Consistent with the existing ReasoningComposer._language() method
    which uses similar thresholds. The difference: _language() returns
    verb phrases ("may", "likely to", "expected to") for sentence
    construction. This function returns bare hedge words for use in
    shorter contexts (notification subjects, dashboard labels).
    """
    if confidence >= 0.70:
        return "expected"
    if confidence >= 0.40:
        return "likely"
    return "might"


# ══════════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════════

# Actions that can cause a false alarm — the gate only operates on these.
# Safe actions (HOLD, CHECK_STOCK, MONITOR) pass through unchanged.
ALERTABLE_ACTIONS = frozenset([
    "ALERT_CRITICAL",
    "ALERT_LOW",
    "REORDER",
])

# Confidence bands (requirement 2)
CONF_FLOOR_HARD   = 0.35   # below → force CHECK_STOCK, no alerts allowed
CONF_FLOOR_MEDIUM = 0.65   # below → max action is MONITOR (no critical alerts)
CONF_HIGH         = 0.80   # required for ALERT_CRITICAL with low variance

# Days since last STOCK_COUNT beyond which the gate considers data stale.
# Derived from business-type cadence in _staleness_threshold(); these are
# the fallback bounds when the baseline service is unavailable.
STALENESS_FALLBACK_DAYS = 10   # used when bootstrap service is unreachable
STALENESS_MIN_DAYS      = 4    # never gate below this (avoids over-suppression)
STALENESS_MAX_DAYS      = 21   # never gate above this (avoids under-suppression)

# Minimum sale events needed before high-severity actions are allowed.
# Products with fewer events are on cold-start priors.
MIN_EVENTS_FOR_ALERT = 3
MIN_EVENTS_FOR_CRITICAL = 5

# Coefficient of variation ceiling for ALERT_CRITICAL.
# CV above this means burn-rate variance is too high to assert "critical".
MAX_CV_FOR_CRITICAL = 0.80

# Post-acknowledgement cooldown multiplier.
# Standard cooldown × this factor = window during which acknowledged
# decisions suppress re-fire.
ACK_COOLDOWN_MULTIPLIER = 2.5

# Spike detection: if latest burn rate is this much higher than the previous
# period AND computed from very few events, it's treated as a spike.
SPIKE_RATE_RATIO_THRESHOLD = 1.60
SPIKE_MAX_EVENTS = 2

# Downgrade map: what to substitute when an alert must be softened one level
DOWNGRADE_ONE_LEVEL = {
    "ALERT_CRITICAL": "ALERT_LOW",
    "ALERT_LOW":      "REORDER",
    "REORDER":        "MONITOR",
}

# Standard cooldown hours by action (mirrors decision.py ACTION_TTL_HOURS)
STANDARD_COOLDOWN_HOURS = {
    "ALERT_CRITICAL": 6,
    "ALERT_LOW":      12,
    "REORDER":        24,
    "CHECK_STOCK":    48,
    "MONITOR":        24,
    "HOLD":           48,
}


# ══════════════════════════════════════════════════════════════════════════════
# Output dataclass
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GateResult:
    """
    The output of DecisionConfidenceGate.evaluate().

    Callers replace action and confidence with final_action and
    final_confidence before persisting the DecisionLog.

    was_gated:       True when the original action was changed.
    gate_note:       Why it was changed (stored on DecisionLog.trust_gate_note).
    original_action: The ActionSelector's raw recommendation before gating.
    final_action:    The approved action after gating.
    final_confidence:The approved confidence after any downward adjustment.
    """
    final_action:    str
    final_confidence: float
    was_gated:       bool
    gate_note:       str
    original_action: str


# ══════════════════════════════════════════════════════════════════════════════
# Main gate
# ══════════════════════════════════════════════════════════════════════════════

class DecisionConfidenceGate:
    """
    Evaluates whether a proposed action has sufficient evidence to be shown.

    Filters run in this order (first match wins):
      1. Hard confidence floor     — confidence < 0.35 → CHECK_STOCK
      2. Medium confidence band    — 0.35 ≤ conf < 0.65 → max MONITOR
      3. High-variance critical    — ALERT_CRITICAL with high CV → ALERT_LOW
      4. Maturity gate             — too few events for high-severity action
      5. Staleness gate            — no recent physical count for high-severity
      6. Multi-signal validation   — missing forecast or sales signal
      7. Post-acknowledgement      — user acknowledged recently → CHECK_STOCK
      8. Spike hold                — anomalous rate spike → one-level downgrade

    Call evaluate() once per decision cycle. The result is immutable.
    """

    def evaluate(
        self,
        proposed_action:     str,
        proposed_confidence: float,
        ctx,                          # DecisionContext from decision.py
    ) -> GateResult:
        """
        Run all filters against the proposed action and return a GateResult.

        ctx is a DecisionContext dataclass (from decision.py). It carries:
          ctx.product              — Product ORM instance
          ctx.forecast             — ForecastResult dataclass
          ctx.confidence_score     — float 0–1
          ctx.stockout_risk        — float 0–1
          ctx.days_until_stockout  — Optional[float]
          ctx.days_until_stockout_pessimistic — Optional[float]
        """
        # Safe actions bypass the gate entirely
        if proposed_action not in ALERTABLE_ACTIONS:
            return GateResult(
                final_action     = proposed_action,
                final_confidence = proposed_confidence,
                was_gated        = False,
                gate_note        = "",
                original_action  = proposed_action,
            )

        # Run filters in priority order
        for filter_fn in [
            self._filter_hard_confidence_floor,
            self._filter_medium_confidence_band,
            self._filter_high_variance_critical,
            self._filter_maturity_gate,
            self._filter_staleness_gate,
            self._filter_multi_signal_validation,
            self._filter_post_acknowledgement_cooldown,
            self._filter_spike_hold,
        ]:
            result = filter_fn(proposed_action, proposed_confidence, ctx)
            if result is not None:
                # This filter triggered — log and return
                logger.info(
                    "Trust gate triggered for %s: %s → %s | %s",
                    ctx.product.sku,
                    proposed_action,
                    result.final_action,
                    result.gate_note[:80],
                )
                return result

        # All filters passed — action is approved unchanged
        return GateResult(
            final_action     = proposed_action,
            final_confidence = proposed_confidence,
            was_gated        = False,
            gate_note        = "",
            original_action  = proposed_action,
        )

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 1 — Hard confidence floor
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_hard_confidence_floor(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        Requirement 2, rule 1: confidence < 0.35 → force CHECK_STOCK.
        No alert is allowed when the model barely knows what is happening.
        """
        if confidence >= CONF_FLOOR_HARD:
            return None

        note = (
            f"Confidence too low for an alert ({int(confidence * 100)}% < "
            f"{int(CONF_FLOOR_HARD * 100)}%). The system cannot make a reliable "
            f"recommendation until more data is recorded. "
            f"A stock count will help restore confidence."
        )
        return self._make_result(action, "CHECK_STOCK",
                                 max(confidence, 0.05), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 2 — Medium confidence band
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_medium_confidence_band(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        Requirement 2, rule 2: 0.35 ≤ confidence < 0.65 → max action is MONITOR.
        No critical alerts in the medium band.
        """
        if confidence >= CONF_FLOOR_MEDIUM:
            return None

        # REORDER and ALERT_* are both blocked in the medium band
        note = (
            f"Confidence is in the medium range ({int(confidence * 100)}%). "
            f"Alerts are reserved for higher-confidence situations. "
            f"The system will monitor this product and escalate when evidence strengthens."
        )
        return self._make_result(action, "MONITOR",
                                 round(confidence * 0.90, 4), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 3 — High-variance critical gate
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_high_variance_critical(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        Requirement 2, rule 4: ALERT_CRITICAL requires confidence >= 0.80
        AND low burn-rate variance (CV ≤ MAX_CV_FOR_CRITICAL).

        A critical alert from a high-variance model is likely a false alarm.
        ALERT_LOW is the appropriate substitute.
        """
        if action != "ALERT_CRITICAL":
            return None

        burn_rate = ctx.forecast.burn_rate_used or 0.0
        burn_std  = ctx.forecast.burn_rate_std_dev or 0.0

        # Compute CV
        cv = (burn_std / burn_rate) if burn_rate > 0 else 1.0

        needs_downgrade = False
        reasons = []

        if confidence < CONF_HIGH:
            needs_downgrade = True
            reasons.append(
                f"confidence is {int(confidence * 100)}% "
                f"(critical alerts require {int(CONF_HIGH * 100)}%+)"
            )

        if cv > MAX_CV_FOR_CRITICAL:
            needs_downgrade = True
            reasons.append(
                f"burn-rate variance is high (CV={cv:.2f}, "
                f"ceiling is {MAX_CV_FOR_CRITICAL:.2f})"
            )

        if not needs_downgrade:
            return None

        note = (
            f"ALERT_CRITICAL downgraded to ALERT_LOW because "
            f"{' and '.join(reasons)}. "
            f"The situation warrants attention but not an urgent alarm."
        )
        return self._make_result(action, "ALERT_LOW",
                                 round(confidence * 0.88, 4), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 4 — Maturity gate (cold-start protection)
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_maturity_gate(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        High-severity actions require a minimum number of real sale events
        in the backing BurnRate. Products on cold-start priors (sample=0)
        cannot produce alerts.

        ALERT_CRITICAL requires MIN_EVENTS_FOR_CRITICAL.
        ALERT_LOW and REORDER require MIN_EVENTS_FOR_ALERT.
        """
        from apps.inventory.models import BurnRate

        latest = (
            BurnRate.objects
            .filter(product=ctx.product)
            .order_by("-computed_at")
            .values("sample_event_count")
            .first()
        )
        event_count = latest["sample_event_count"] if latest else 0

        required = (
            MIN_EVENTS_FOR_CRITICAL
            if action == "ALERT_CRITICAL"
            else MIN_EVENTS_FOR_ALERT
        )

        if event_count >= required:
            return None

        if event_count == 0:
            note = (
                f"No sales data recorded yet for {ctx.product.sku}. "
                f"The alert is based on industry estimates, not observed patterns. "
                f"Record {required} or more sales to unlock accurate alerts."
            )
        else:
            note = (
                f"Only {event_count} sale event(s) recorded for {ctx.product.sku} "
                f"({required} required for {action.replace('_', ' ').lower()}). "
                f"Recording more sales will enable confident alerts."
            )

        return self._make_result(action, "CHECK_STOCK",
                                 min(confidence, 0.40), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 5 — Staleness gate (unverified estimated_quantity)
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_staleness_gate(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        Requirement 2: If data is stale → force CHECK_STOCK.

        estimated_quantity drifts over time if informal restocks happen.
        If the product has not been physically counted within the
        business-type-appropriate cadence window (×2 tolerance), the system
        cannot honestly assert a shortage.

        Bypass: if confidence is >= 0.70, the model has incorporated recent
        verified data and drift risk is low.
        """
        # High-confidence models have recent verified signals — don't gate them
        if confidence >= 0.70:
            return None

        last_verified = getattr(ctx.product, "last_verified_at", None)

        if last_verified is None:
            note = (
                f"{ctx.product.sku} has not had a physical stock count yet. "
                f"The estimated quantity is an assumption, not a measurement. "
                f"Record an opening count to enable accurate alerts."
            )
            return self._make_result(action, "CHECK_STOCK",
                                     min(confidence, 0.35), note)

        stale_threshold = self._staleness_threshold(ctx.product)
        days_stale = (timezone.now() - last_verified).days

        if days_stale <= stale_threshold:
            return None

        note = (
            f"The last verified count for {ctx.product.sku} was "
            f"{days_stale} day(s) ago. "
            f"Alerts require a count within the last {stale_threshold} days. "
            f"A quick stock count will restore alert accuracy immediately."
        )
        return self._make_result(action, "CHECK_STOCK",
                                 min(confidence, 0.40), note)

    def _staleness_threshold(self, product) -> int:
        """
        Returns max acceptable days since last count for this product's
        business type. Clamped to [STALENESS_MIN_DAYS, STALENESS_MAX_DAYS].
        """
        try:
            from apps.engine.bootstrap import BusinessTypeBaselineService
            baseline = BusinessTypeBaselineService().get(product.owner)
            raw = baseline.verification_cadence_days * 2.0
        except Exception:
            raw = float(STALENESS_FALLBACK_DAYS)
        return int(min(STALENESS_MAX_DAYS, max(STALENESS_MIN_DAYS, raw)))

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 6 — Multi-signal validation
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_multi_signal_validation(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        Requirement 3: require at least forecast signal + recent sales.

        A decision needs corroborating evidence from multiple streams.
        If either the forecast was skipped or there are no recent sales,
        downgrade to MONITOR rather than acting on a single signal alone.
        """
        missing = []

        # Check 1: forecast must not be skipped / zero-burn
        if ctx.forecast.skipped or ctx.forecast.burn_rate_used <= 0:
            missing.append("a valid forecast")

        # Check 2: recent sales activity (any sale in last 14 days)
        from apps.inventory.models import InventoryEvent
        recent_sale = InventoryEvent.objects.filter(
            product    = ctx.product,
            event_type = InventoryEvent.SALE,
            occurred_at__gte = timezone.now() - timedelta(days=14),
        ).exists()

        if not recent_sale:
            missing.append("recent sales activity (last 14 days)")

        if not missing:
            return None

        note = (
            f"Alert downgraded to MONITOR because the decision lacks "
            f"corroborating evidence: missing {' and '.join(missing)}. "
            f"The system needs both a valid forecast and recent sales before "
            f"it can assert a strong recommendation."
        )
        return self._make_result(action, "MONITOR",
                                 round(confidence * 0.80, 4), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 7 — Post-acknowledgement cooldown
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_post_acknowledgement_cooldown(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        When a user acknowledges a decision, the standard cooldown in
        ActionSelector._is_on_cooldown() stops applying (it only checks
        unacknowledged decisions).

        This filter extends the suppression: an acknowledged action is
        re-suppressed for ACK_COOLDOWN_MULTIPLIER × the standard window.

        Without this, a sale event 5 minutes after acknowledgement would
        re-fire the same alert immediately.
        """
        from apps.inventory.models import DecisionLog

        base_hours = STANDARD_COOLDOWN_HOURS.get(action, 24)
        ack_hours  = base_hours * ACK_COOLDOWN_MULTIPLIER
        ack_cutoff = timezone.now() - timedelta(hours=ack_hours)

        recently_acknowledged = DecisionLog.objects.filter(
            product          = ctx.product,
            action           = action,
            is_acknowledged  = True,
            acknowledged_at__gte = ack_cutoff,
        ).exists()

        if not recently_acknowledged:
            return None

        note = (
            f"This alert was recently acknowledged. "
            f"The system suppresses re-firing for {int(ack_hours):.0f} hours "
            f"after acknowledgement to prevent alert fatigue. "
            f"If conditions deteriorate further, a new alert will follow."
        )
        # Substitute CHECK_STOCK so the product stays visible in the dashboard
        return self._make_result(action, "CHECK_STOCK",
                                 round(confidence * 0.70, 4), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Filter 8 — Spike hold
    # ══════════════════════════════════════════════════════════════════════════

    def _filter_spike_hold(
        self, action: str, confidence: float, ctx
    ) -> Optional[GateResult]:
        """
        A single anomalous sale event can double the burn rate in one learning
        cycle. If the latest BurnRate was computed from very few events and
        is significantly higher than the preceding period, the urgency is
        overstated. Downgrade one level rather than suppressing entirely —
        the risk is real, the timing may not be.
        """
        from apps.inventory.models import BurnRate

        burns = list(
            BurnRate.objects
            .filter(product=ctx.product, sample_event_count__gt=0)
            .order_by("-computed_at")
            .values("burn_rate_per_day", "sample_event_count")[:2]
        )

        if len(burns) < 2:
            return None

        latest   = burns[0]
        previous = burns[1]

        if previous["burn_rate_per_day"] <= 0:
            return None

        rate_ratio = latest["burn_rate_per_day"] / previous["burn_rate_per_day"]

        is_spike = (
            latest["sample_event_count"] <= SPIKE_MAX_EVENTS
            and rate_ratio >= SPIKE_RATE_RATIO_THRESHOLD
        )

        if not is_spike:
            return None

        substitute = DOWNGRADE_ONE_LEVEL.get(action)
        if substitute is None:
            return None

        pct = int((rate_ratio - 1.0) * 100)
        note = (
            f"Consumption for {ctx.product.sku} appears to have spiked "
            f"({pct}% above the prior period) based on only "
            f"{latest['sample_event_count']} event(s). "
            f"The alert has been softened by one level while the pattern "
            f"stabilises. If high consumption continues, a stronger alert "
            f"will follow in the next cycle."
        )
        return self._make_result(action, substitute,
                                 round(confidence * 0.85, 4), note)

    # ══════════════════════════════════════════════════════════════════════════
    # Helper
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _make_result(
        original:    str,
        substitute:  str,
        confidence:  float,
        note:        str,
    ) -> GateResult:
        return GateResult(
            final_action     = substitute,
            final_confidence = round(max(0.05, confidence), 4),
            was_gated        = True,
            gate_note        = note,
            original_action  = original,
        )