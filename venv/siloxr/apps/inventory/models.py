# backend/apps/inventory/models.py

import uuid
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Product(models.Model):
    """
    A product is NOT a quantity record.
    It is a subject of observation, prediction, and decision.

    INVARIANT: estimated_quantity and last_verified_quantity must NEVER be merged.
    - last_verified_quantity → physical ground truth (set only by STOCK_COUNT events)
    - estimated_quantity     → system's running prediction (updated by Learning Engine)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="products",
    )

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    unit = models.CharField(max_length=50, default="units")
    category = models.CharField(max_length=100, blank=True)
    reorder_point = models.PositiveIntegerField(default=0)
    reorder_quantity = models.PositiveIntegerField(default=0)
    selling_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional selling price used to estimate revenue at risk.",
    )
    cost_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional unit cost used to estimate margin at risk.",
    )

    # ── Quantity fields: these two MUST stay separate ──────────────────────
    last_verified_quantity = models.IntegerField(
        default=0,
        help_text="Physical count. Only updated by STOCK_COUNT events.",
    )
    last_verified_at = models.DateTimeField(null=True, blank=True)

    estimated_quantity = models.FloatField(
        default=0.0,
        help_text="System prediction. Updated by Learning Engine after every event.",
    )
    # ───────────────────────────────────────────────────────────────────────

    # Confidence in the current estimated_quantity (0.0–1.0)
    confidence_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How confident the system is in estimated_quantity.",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_product"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "is_active"]),
            models.Index(fields=["sku"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"

    @property
    def quantity_gap(self) -> float:
        """Difference between verified and estimated. High gap = low confidence."""
        return abs(self.last_verified_quantity - self.estimated_quantity)

    @property
    def current_stock(self) -> float:
        """Current operating stock view used by higher-level insight engines."""
        estimated = float(self.estimated_quantity or 0.0)
        verified = float(self.last_verified_quantity or 0.0)
        return estimated if estimated > 0 else verified

    @property
    def needs_verification(self) -> bool:
        """True when confidence is low enough to warrant a physical count."""
        return self.confidence_score < 0.4

    @property
    def data_maturity_score(self) -> float:
        """
        Derived fallback for engines that expect maturity scoring.
        Keeps older databases compatible even when no dedicated column exists.
        """
        recent_events = self.events.count()
        event_bonus = min(35.0, recent_events * 4.0)
        verification_bonus = 15.0 if self.last_verified_at else 0.0
        confidence_component = max(0.0, min(100.0, self.confidence_score * 50.0))
        return round(min(100.0, confidence_component + event_bonus + verification_bonus), 2)

    @property
    def maturity_tier(self) -> str:
        score = self.data_maturity_score
        if score >= 80:
            return "high"
        if score >= 55:
            return "medium"
        if score >= 30:
            return "low"
        return "early"


class InventoryEvent(models.Model):
    """
    THE only legal mechanism for changing inventory state.

    Every sale, restock, adjustment, or count flows through here.
    This is the time-series backbone — the Learning Engine reads
    this table exclusively to compute burn rates.

    DO NOT update Product.estimated_quantity directly. Always create an event.
    """

    # ── Event types ────────────────────────────────────────────────────────
    SALE = "SALE"
    RESTOCK = "RESTOCK"
    STOCK_COUNT = "STOCK_COUNT"   # Physical verification event — updates last_verified_quantity
    ADJUSTMENT = "ADJUSTMENT"     # Manual correction with a reason
    WASTE = "WASTE"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"

    EVENT_TYPE_CHOICES = [
        (SALE, "Sale"),
        (RESTOCK, "Restock"),
        (STOCK_COUNT, "Stock count"),
        (ADJUSTMENT, "Adjustment"),
        (WASTE, "Waste"),
        (TRANSFER_IN, "Transfer in"),
        (TRANSFER_OUT, "Transfer out"),
    ]

    # Events that reduce stock
    OUTBOUND_EVENTS = {SALE, WASTE, TRANSFER_OUT}
    # Events that increase stock
    INBOUND_EVENTS = {RESTOCK, TRANSFER_IN}
    # ───────────────────────────────────────────────────────────────────────

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="events",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="inventory_events",
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    quantity = models.FloatField(
        help_text="Always positive. Direction is inferred from event_type.",
        validators=[MinValueValidator(0.0)],
    )

    # For STOCK_COUNT events: the physically counted value
    verified_quantity = models.IntegerField(
        null=True,
        blank=True,
        help_text="Physical count. Populated only for STOCK_COUNT events.",
    )

    notes = models.TextField(blank=True)

    # Offline support: was this event queued locally before syncing?
    is_offline_event = models.BooleanField(default=False)
    client_event_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Client-generated UUID for deduplication on sync.",
    )

    occurred_at = models.DateTimeField(
        help_text="When the event actually happened (may differ from created_at for offline events).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_event"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["product", "occurred_at"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["client_event_id"]),  # dedup index
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["client_event_id"],
                condition=models.Q(client_event_id__isnull=False),
                name="unique_client_event_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.event_type} × {self.quantity} → {self.product.sku} @ {self.occurred_at:%Y-%m-%d %H:%M}"

    @property
    def signed_quantity(self) -> float:
        """Returns the quantity with direction applied (+/-).
        Used by the Learning Engine to compute net inventory changes."""
        if self.event_type in self.OUTBOUND_EVENTS:
            return -self.quantity
        if self.event_type in self.INBOUND_EVENTS:
            return self.quantity
        if self.event_type == self.STOCK_COUNT:
            # Net delta between verified count and last known estimate
            if self.verified_quantity is not None and self.product.estimated_quantity:
                return self.verified_quantity - self.product.estimated_quantity
        return 0.0


class BurnRate(models.Model):
    """
    The Learning Engine's output for a single product.

    burn_rate_per_day is the key signal used by the Forecast Engine.
    It is NEVER manually set — only the Learning Engine writes here.

    Multiple records exist per product (one per learning cycle),
    allowing us to track how the burn rate evolves over time.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="burn_rates",
    )

    burn_rate_per_day = models.FloatField(
        help_text="Average units consumed per day, learned from recent SALE events.",
        validators=[MinValueValidator(0.0)],
    )

    # Uncertainty in the burn rate itself
    burn_rate_std_dev = models.FloatField(
        default=0.0,
        help_text="Standard deviation of daily consumption. Used for uncertainty bands.",
        validators=[MinValueValidator(0.0)],
    )

    # How many days of data this rate is based on
    sample_days = models.PositiveIntegerField(default=0)
    sample_event_count = models.PositiveIntegerField(default=0)

    # Confidence in this burn rate (0.0–1.0)
    confidence_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    # Learning window used (e.g., last 30 days)
    window_days = models.PositiveIntegerField(default=30)
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_burn_rate"
        ordering = ["-computed_at"]
        get_latest_by = "computed_at"
        indexes = [
            models.Index(fields=["product", "computed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.sku}: {self.burn_rate_per_day:.2f}/day (conf={self.confidence_score:.0%})"

    @property
    def days_remaining(self) -> float | None:
        """Estimated days of stock remaining based on current estimated_quantity."""
        if self.burn_rate_per_day <= 0:
            return None
        return self.product.estimated_quantity / self.burn_rate_per_day


class ForecastSnapshot(models.Model):
    """
    A point-in-time prediction of future inventory levels.
    Produced by the Forecast Engine and stored here for two reasons:
      1. Drive UI (forecast strip, trend chart)
      2. Be compared against actuals later by the Feedback Engine

    The uncertainty fields (lower/upper bound) are non-optional.
    A forecast without uncertainty is not a forecast — it is a guess.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="forecasts",
    )
    burn_rate = models.ForeignKey(
        BurnRate,
        on_delete=models.SET_NULL,
        null=True,
        related_name="forecasts",
        help_text="The burn rate snapshot used to produce this forecast.",
    )

    # The forecast horizon
    forecast_date = models.DateField(
        help_text="The future date being predicted.",
    )
    predicted_quantity = models.FloatField(
        help_text="Central estimate of inventory on forecast_date.",
    )

    # Uncertainty band — MANDATORY
    lower_bound = models.FloatField(
        help_text="Pessimistic estimate (high burn scenario).",
    )
    upper_bound = models.FloatField(
        help_text="Optimistic estimate (low burn scenario).",
    )

    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )

    # Feedback fields — populated by Feedback Engine after the date passes
    actual_quantity = models.FloatField(
        null=True,
        blank=True,
        help_text="Actual quantity on forecast_date. Populated after the fact.",
    )
    forecast_error = models.FloatField(
        null=True,
        blank=True,
        help_text="predicted_quantity − actual_quantity. Populated by Feedback Engine.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_forecast_snapshot"
        ordering = ["-forecast_date"]
        indexes = [
            models.Index(fields=["product", "forecast_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "forecast_date"],
                name="unique_product_forecast_date",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.product.sku} @ {self.forecast_date}: "
            f"{self.predicted_quantity:.1f} [{self.lower_bound:.1f}–{self.upper_bound:.1f}]"
        )

    @property
    def is_resolvable(self) -> bool:
        """True when the forecast date has passed and can be evaluated."""
        from django.utils import timezone
        from datetime import date
        return self.forecast_date <= date.today() and self.actual_quantity is None


class DecisionLog(models.Model):
    """
    The Decision Engine's output — a structured recommendation.

    This is the core monetized object. Pro users see this. Free users don't.

    Every decision includes:
    - action: what to do
    - reasoning: why (human-readable string)
    - confidence_score: how certain the system is
    - expires_at: when this decision is no longer relevant

    Decisions are NEVER commands. They are suggestions with reasoning.
    The UI tone rule: "may need reorder" not "reorder now".
    """

    # ── Decision actions ────────────────────────────────────────────────
    REORDER = "REORDER"
    CHECK_STOCK = "CHECK_STOCK"
    HOLD = "HOLD"
    ALERT_LOW = "ALERT_LOW"
    ALERT_CRITICAL = "ALERT_CRITICAL"
    MONITOR = "MONITOR"

    ACTION_CHOICES = [
        (REORDER, "Consider reorder"),
        (CHECK_STOCK, "Verify stock count"),
        (HOLD, "No action needed"),
        (ALERT_LOW, "Stock running low"),
        (ALERT_CRITICAL, "Stock critically low"),
        (MONITOR, "Monitor trend"),
    ]

    STATUS_SUGGESTED = "suggested"
    STATUS_VIEWED = "viewed"
    STATUS_ACTED = "acted"
    STATUS_IGNORED = "ignored"

    STATUS_CHOICES = [
        (STATUS_SUGGESTED, "Suggested"),
        (STATUS_VIEWED, "Viewed"),
        (STATUS_ACTED, "Acted"),
        (STATUS_IGNORED, "Ignored"),
    ]

    # Severity mapping for UI treatment
    ACTION_SEVERITY = {
        ALERT_CRITICAL: "critical",
        ALERT_LOW: "warning",
        REORDER: "warning",
        CHECK_STOCK: "info",
        MONITOR: "info",
        HOLD: "ok",
    }
    # ───────────────────────────────────────────────────────────────────

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    forecast = models.ForeignKey(
        ForecastSnapshot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
        help_text="The forecast snapshot that triggered this decision.",
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reasoning = models.TextField(
        help_text="Human-readable explanation of why this action was recommended.",
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence that this action is correct (0.0–1.0).",
    )

    # Contextual snapshot at decision time
    estimated_quantity_at_decision = models.FloatField()
    days_remaining_at_decision = models.FloatField(null=True, blank=True)
    burn_rate_at_decision = models.FloatField(null=True, blank=True)
    estimated_lost_sales = models.FloatField(default=0.0)
    estimated_revenue_loss = models.FloatField(default=0.0)
    risk_score = models.FloatField(default=0.0)
    priority_score = models.FloatField(default=0.0)
    trust_gate_note = models.TextField(
            blank=True,
            default="",
            help_text=(
                "Populated when DecisionConfidenceGate downgraded this decision. "
                "Explains why the original action was softened. "
                "Stored for audit and admin review — not shown in the user-facing UI."
            ),
        )
    original_action = models.CharField(
            max_length=30,
            blank=True,
            default="",
            help_text=(
                "The ActionSelector's raw recommendation before the trust gate ran. "
                "Empty when the gate did not fire (action == original)."
            ),
        )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SUGGESTED,
    )
    viewed_at = models.DateTimeField(null=True, blank=True)
    acted_at = models.DateTimeField(null=True, blank=True)
    outcome_label = models.CharField(max_length=100, blank=True, default="")

    is_acknowledged = models.BooleanField(
        default=False,
        help_text="Has the user acknowledged this decision?",
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(
        help_text="When this decision should be superseded by a fresh one.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_decision_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "is_acknowledged", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} for {self.product.sku} (conf={self.confidence_score:.0%})"

    @property
    def severity(self) -> str:
        return self.ACTION_SEVERITY.get(self.action, "info")

    @property
    def is_expired(self) -> bool:
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @property
    def is_active(self) -> bool:
        return (
            not self.is_expired
            and not self.is_acknowledged
            and self.status not in {self.STATUS_ACTED, self.STATUS_IGNORED}
        )

    def mark_viewed(self, save: bool = True) -> None:
        from django.utils import timezone

        if self.status == self.STATUS_SUGGESTED:
            self.status = self.STATUS_VIEWED
            self.viewed_at = self.viewed_at or timezone.now()
            if save:
                self.save(update_fields=["status", "viewed_at"])

    def mark_acted(self, outcome_label: str = "", save: bool = True) -> None:
        from django.utils import timezone

        now = timezone.now()
        self.status = self.STATUS_ACTED
        self.acted_at = now
        self.is_acknowledged = True
        self.acknowledged_at = self.acknowledged_at or now
        if outcome_label:
            self.outcome_label = outcome_label
        if save:
            self.save(
                update_fields=[
                    "status",
                    "acted_at",
                    "is_acknowledged",
                    "acknowledged_at",
                    "outcome_label",
                ]
            )

    def mark_ignored(self, save: bool = True) -> None:
        from django.utils import timezone

        now = timezone.now()
        self.status = self.STATUS_IGNORED
        self.is_acknowledged = True
        self.acknowledged_at = self.acknowledged_at or now
        if save:
            self.save(
                update_fields=["status", "is_acknowledged", "acknowledged_at"]
            )
    

# backend/apps/inventory/models.py — ADD new model

class InsightFeedback(models.Model):
    """
    User feedback on an insight/decision.
    Stored for future model improvement via the Feedback Engine.
    """
    RATING_HELPFUL    = "helpful"
    RATING_UNHELPFUL  = "unhelpful"
    RATING_ACCURATE   = "accurate"
    RATING_INACCURATE = "inaccurate"

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="insight_feedback"
    )
    decision    = models.ForeignKey(
        "DecisionLog", on_delete=models.CASCADE, null=True, blank=True,
        related_name="feedback"
    )
    detector    = models.CharField(max_length=50, blank=True, default="")
    product     = models.ForeignKey(
        "Product", on_delete=models.CASCADE, null=True, blank=True
    )
    was_helpful  = models.BooleanField(null=True, blank=True)
    was_accurate = models.BooleanField(null=True, blank=True)
    comment      = models.TextField(blank=True, default="")
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_insight_feedback"
        indexes  = [models.Index(fields=["user", "created_at"])]


class UserBehaviorLog(models.Model):
    EVENT_DECISION_VIEWED = "decision_viewed"
    EVENT_DECISION_ACTED = "decision_acted"
    EVENT_DECISION_IGNORED = "decision_ignored"
    EVENT_PRODUCT_UPDATED = "product_updated"

    EVENT_CHOICES = [
        (EVENT_DECISION_VIEWED, "Decision viewed"),
        (EVENT_DECISION_ACTED, "Decision acted"),
        (EVENT_DECISION_IGNORED, "Decision ignored"),
        (EVENT_PRODUCT_UPDATED, "Product updated"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="behavior_logs",
    )
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="behavior_logs",
    )
    decision = models.ForeignKey(
        "DecisionLog",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="behavior_logs",
    )
    event_type = models.CharField(max_length=40, choices=EVENT_CHOICES)
    interaction_time_ms = models.PositiveIntegerField(null=True, blank=True)
    product_update_frequency = models.FloatField(default=0.0)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_user_behavior_log"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["user", "event_type", "occurred_at"]),
            models.Index(fields=["product", "occurred_at"]),
        ]


class ReorderRecord(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PLACED = "placed"
    STATUS_RECEIVED = "received"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PLACED, "Placed"),
        (STATUS_RECEIVED, "Received"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reorder_records",
    )
    decision = models.ForeignKey(
        DecisionLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reorder_records",
    )
    suggested_quantity = models.PositiveIntegerField(default=0)
    suggested_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_reorder_record"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Reorder {self.product.sku} ({self.status})"
