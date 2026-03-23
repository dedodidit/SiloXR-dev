# backend/apps/api/serializers.py

from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers

from apps.inventory.models import (
    DecisionLog,
    ForecastSnapshot,
    InventoryEvent,
    Product,
    ReorderRecord,
)
from apps.inventory.events import EventProcessor, EventProcessingError
from apps.engine.trust import get_confidence_phrase
from apps.engine.confidence import ConfidenceScorer



class DashboardSummarySerializer(serializers.Serializer):
    total_products = serializers.IntegerField()
    total_stock = serializers.IntegerField()
    low_stock_count = serializers.IntegerField()
    recent_events = serializers.IntegerField()

# ── Shared field mixins ────────────────────────────────────────────────────────

class ConfidenceFieldsMixin:
    """
    Adds a human-readable confidence label alongside the raw score.
    Used by any serializer that surfaces confidence_score.
    """
    def get_confidence_label(self, obj) -> str:
        score = getattr(obj, "confidence_score", 0)
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "moderate"
        if score >= 0.20:
            return "low"
        return "very_low"


# ── Product serializers ────────────────────────────────────────────────────────

class ProductListSerializer(
    ConfidenceFieldsMixin, serializers.ModelSerializer
):
    """
    Lightweight serializer for list views.
    Includes the active decision and days-remaining signal
    so the product table can show decision state without extra requests.
    """
    confidence_label      = serializers.SerializerMethodField()
    active_decision       = serializers.SerializerMethodField()
    days_remaining        = serializers.SerializerMethodField()
    needs_verification    = serializers.BooleanField(read_only=True)
    quantity_gap          = serializers.FloatField(read_only=True)

    class Meta:
        model  = Product
        fields = [
            "id", "name", "sku", "unit", "category",
            "selling_price", "cost_price",
            "last_verified_quantity", "last_verified_at",
            "estimated_quantity",
            "confidence_score", "confidence_label",
            "reorder_point", "reorder_quantity",
            "needs_verification", "quantity_gap",
            "active_decision", "days_remaining",
            "is_active", "updated_at",
        ]
        read_only_fields = [
            "id", "estimated_quantity", "confidence_score",
            "last_verified_at", "updated_at",
        ]

    def get_confidence_label(self, obj):
        return super().get_confidence_label(obj)

    def get_active_decision(self, obj) -> dict | None:
        """
        Returns the most recent unexpired, unacknowledged decision.
        Returns None for Free users (pro gate in view; serializer stays neutral).
        """
        decision = (
            DecisionLog.objects
            .filter(
                product=obj,
                is_acknowledged=False,
                expires_at__gt=timezone.now(),
            )
            .exclude(
                status__in=[DecisionLog.STATUS_ACTED, DecisionLog.STATUS_IGNORED]
            )
            .order_by("-created_at")
            .first()
        )
        if decision is None:
            return None
        return {
            "id":               str(decision.id),
            "action":           decision.action,
            "severity":         decision.severity,
            "confidence_score": decision.confidence_score,
            "reasoning":        decision.reasoning,
            "created_at":       decision.created_at,
        }

    def get_days_remaining(self, obj) -> float | None:
        """
        Days of stock remaining based on the latest burn rate.
        Available to all tiers — it's a number, not a decision.
        """
        burn = (
            obj.burn_rates
            .order_by("-computed_at")
            .first()
        )
        if burn is None:
            return None
        return burn.days_remaining


class ProductDetailSerializer(ProductListSerializer):
    """
    Full serializer for the product detail endpoint.
    Adds recent events and the near-horizon forecast strip.
    """
    recent_events    = serializers.SerializerMethodField()
    forecast_strip   = serializers.SerializerMethodField()
    burn_rate        = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "recent_events", "forecast_strip", "burn_rate",
            "created_at",
        ]

    def get_recent_events(self, obj) -> list:
        events = (
            obj.events
            .order_by("-occurred_at")[:20]
        )
        return InventoryEventSerializer(events, many=True).data

    def get_forecast_strip(self, obj) -> list:
        """
        7-day forecast strip: days 1, 3, 7 and any key threshold crossings.
        Compact format for the frontend strip component.
        """
        key_offsets = {1, 3, 7}
        today = timezone.now().date()
        snapshots = (
            ForecastSnapshot.objects
            .filter(
                product=obj,
                forecast_date__gte=today,
                forecast_date__lte=today + timedelta(days=7),
            )
            .order_by("forecast_date")
        )
        return ForecastStripSerializer(snapshots, many=True).data

    def get_burn_rate(self, obj) -> dict | None:
        burn = obj.burn_rates.order_by("-computed_at").first()
        if burn is None:
            return None
        return {
            "rate_per_day":   burn.burn_rate_per_day,
            "std_dev":        burn.burn_rate_std_dev,
            "confidence":     burn.confidence_score,
            "sample_days":    burn.sample_days,
            "computed_at":    burn.computed_at,
        }


class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Product
        fields = [
            "name", "sku", "unit", "category",
            "reorder_point", "reorder_quantity", "selling_price", "cost_price",
        ]

    def validate_sku(self, value):
        if Product.objects.filter(sku=value).exists():
            raise serializers.ValidationError(
                f"A product with SKU '{value}' already exists."
            )
        return value.upper().strip()


# ── InventoryEvent serializers ─────────────────────────────────────────────────

class InventoryEventSerializer(serializers.ModelSerializer):
    signed_quantity = serializers.FloatField(read_only=True)

    class Meta:
        model  = InventoryEvent
        fields = [
            "id", "event_type", "quantity", "signed_quantity",
            "verified_quantity", "notes",
            "is_offline_event", "client_event_id",
            "occurred_at", "created_at",
        ]
        read_only_fields = ["id", "created_at", "signed_quantity"]


class InventoryEventCreateSerializer(serializers.ModelSerializer):
    """
    Used for both online event creation and offline sync.
    Routes writes through EventProcessor to enforce the time-series contract.
    """
    class Meta:
        model  = InventoryEvent
        fields = [
            "event_type", "quantity", "verified_quantity",
            "notes", "occurred_at",
            "client_event_id", "is_offline_event",
        ]
        extra_kwargs = {
            "client_event_id": {"validators": []},
        }

    def validate(self, data):
        if data.get("event_type") == InventoryEvent.STOCK_COUNT:
            if data.get("verified_quantity") is None:
                raise serializers.ValidationError(
                    {"verified_quantity": "Required for STOCK_COUNT events."}
                )
        if data.get("quantity", 0) < 0:
            raise serializers.ValidationError(
                {"quantity": "Quantity must be positive. Direction is set by event_type."}
            )
        return data

    def create(self, validated_data):
        product    = self.context["product"]
        user       = self.context["request"].user
        processor  = EventProcessor(product)
        try:
            event = processor.record(
                event_type       = validated_data["event_type"],
                quantity         = validated_data["quantity"],
                occurred_at      = validated_data.get("occurred_at"),
                recorded_by      = user,
                notes            = validated_data.get("notes", ""),
                verified_quantity= validated_data.get("verified_quantity"),
                client_event_id  = validated_data.get("client_event_id"),
                is_offline_event = validated_data.get("is_offline_event", False),
            )
        except EventProcessingError as exc:
            raise serializers.ValidationError({"detail": str(exc)})
        return event


class BulkEventSyncItemSerializer(InventoryEventCreateSerializer):
    product_id = serializers.UUIDField()
    client_event_id = serializers.UUIDField(required=False, allow_null=True, validators=[])

    class Meta(InventoryEventCreateSerializer.Meta):
        fields = ["product_id"] + InventoryEventCreateSerializer.Meta.fields


class BulkEventSyncSerializer(serializers.Serializer):
    """
    Accepts a list of offline events for sync.
    Each event is processed independently — partial success is allowed.
    The response reports per-event status so the client can clear
    successfully synced events from its local queue.
    """
    events = BulkEventSyncItemSerializer(many=True)

    def validate_events(self, events):
        if not events:
            raise serializers.ValidationError("events list cannot be empty.")
        if len(events) > 500:
            raise serializers.ValidationError(
                "Maximum 500 events per sync request."
            )
        return events


# ── Forecast serializers ───────────────────────────────────────────────────────

class ForecastSnapshotSerializer(
    ConfidenceFieldsMixin, serializers.ModelSerializer
):
    confidence_label = serializers.SerializerMethodField()
    days_from_today  = serializers.SerializerMethodField()

    class Meta:
        model  = ForecastSnapshot
        fields = [
            "id", "forecast_date",
            "predicted_quantity", "lower_bound", "upper_bound",
            "confidence_score", "confidence_label",
            "actual_quantity", "forecast_error",
            "days_from_today", "created_at",
        ]

    def get_confidence_label(self, obj):
        return super().get_confidence_label(obj)

    def get_days_from_today(self, obj) -> int:
        today = timezone.now().date()
        return (obj.forecast_date - today).days


class ForecastStripSerializer(serializers.ModelSerializer):
    """
    Compact serializer for the 7-day forecast strip component.
    Omits actuals and error fields — those are for accuracy reporting.
    """
    days_from_today = serializers.SerializerMethodField()

    class Meta:
        model  = ForecastSnapshot
        fields = [
            "forecast_date", "predicted_quantity",
            "lower_bound", "upper_bound",
            "confidence_score", "days_from_today",
        ]

    def get_days_from_today(self, obj) -> int:
        return (obj.forecast_date - timezone.now().date()).days


class ForecastAccuracySerializer(serializers.Serializer):
    """
    Read-only serializer for the forecast accuracy endpoint.
    Presents historical error metrics computed by the Feedback Engine.
    """
    product_id       = serializers.UUIDField()
    product_sku      = serializers.CharField()
    resolved_count   = serializers.IntegerField()
    mae              = serializers.FloatField()
    mape             = serializers.FloatField()
    wape             = serializers.FloatField(required=False)
    rmse             = serializers.FloatField(required=False)
    mase             = serializers.FloatField(required=False)
    bias             = serializers.FloatField()
    bias_pct         = serializers.FloatField(required=False)
    interval_coverage = serializers.FloatField(required=False)
    mean_interval_width = serializers.FloatField(required=False)
    calibration_gap  = serializers.FloatField(required=False)
    bias_direction   = serializers.CharField()
    window_days      = serializers.IntegerField()
    errors           = serializers.ListField(required=False)

# backend/apps/api/serializers.py  (append to bottom if missing)

# ── Decision serializers ───────────────────────────────────────────────────────

# backend/apps/api/serializers.py
# EXTEND DecisionLogSerializer — add gated_reasoning field

class DecisionLogSerializer(ConfidenceFieldsMixin, serializers.ModelSerializer):
    confidence_label    = serializers.SerializerMethodField()
    severity            = serializers.CharField(read_only=True)
    is_active           = serializers.BooleanField(read_only=True)
    is_expired          = serializers.BooleanField(read_only=True)
    reasoning           = serializers.SerializerMethodField()
    product_sku         = serializers.CharField(source="product.sku",  read_only=True)
    product_name        = serializers.CharField(source="product.name", read_only=True)
    product_id          = serializers.UUIDField(source="product.id", read_only=True)
    gated_reasoning     = serializers.SerializerMethodField()
    impact              = serializers.FloatField(source="estimated_revenue_loss", read_only=True)
    confidence_level    = serializers.SerializerMethodField()
    confidence_phrase   = serializers.SerializerMethodField()
    data_stale          = serializers.SerializerMethodField()
    assumption_message  = serializers.SerializerMethodField()

    class Meta:
        model  = DecisionLog
        fields = [
            "id", "product_id", "product_sku", "product_name",
            "action", "severity",
            "reasoning", "gated_reasoning",
            "confidence_score", "confidence_label",
            "confidence_level", "confidence_phrase",
            "estimated_quantity_at_decision",
            "days_remaining_at_decision",
            "burn_rate_at_decision",
            "estimated_lost_sales",
            "estimated_revenue_loss",
            "impact",
            "risk_score",
            "priority_score",
            "data_stale",
            "assumption_message",
            "status",
            'impact_summary',
            "viewed_at",
            "acted_at",
            "outcome_label",
            "is_acknowledged", "acknowledged_at",
            "is_active", "is_expired",
            "expires_at", "created_at",
        ]
        read_only_fields = [
            "id", "action", "severity",
            "confidence_score",
            "estimated_quantity_at_decision",
            "days_remaining_at_decision",
            "is_active", "is_expired", "created_at",
        ]
    # backend/apps/api/serializers.py
# EXTEND DecisionLogSerializer — add revenue impact fields
    gated_reasoning        = serializers.SerializerMethodField()
    impact_summary         = serializers.SerializerMethodField()  # NEW

    def get_impact_summary(self, obj) -> dict:
        """
        Returns the commercial impact estimate in a format the frontend
        can render as: 'You may lose ~₦12,400 if this is not addressed.'
        Only shown to Pro users.
        """
        request = self.context.get("request")
        if not request or not request.user.is_pro:
            return {"visible": False}

        lost  = getattr(obj, "estimated_lost_sales", 0) or 0
        rev   = getattr(obj, "estimated_revenue_loss", 0) or 0

        if lost <= 0:
            return {"visible": False}

        return {
            "visible":              True,
            "lost_sales_units":     round(lost, 1),
            "revenue_loss":         round(rev, 2),
            "has_revenue_estimate": rev > 0,
        }

    def get_confidence_label(self, obj):
        return super().get_confidence_label(obj)

    def get_confidence_level(self, obj) -> str:
        return self.get_confidence_label(obj)

    def get_confidence_phrase(self, obj) -> str:
        return get_confidence_phrase(getattr(obj, "confidence_score", 0.0))

    def get_data_stale(self, obj) -> bool:
        latest_event = obj.product.events.order_by("-occurred_at").first()
        if latest_event is None:
            return True
        age_days = max(0.0, (timezone.now() - latest_event.occurred_at).total_seconds() / 86400.0)
        return age_days > ConfidenceScorer.STALE_DATA_THRESHOLD_DAYS

    def get_assumption_message(self, obj) -> str:
        burn_rate = getattr(getattr(obj, "forecast", None), "burn_rate", None)
        if burn_rate and int(getattr(burn_rate, "sample_event_count", 0) or 0) == 0:
            return "Using baseline assumptions due to limited data"
        return ""

    def get_reasoning(self, obj) -> str:
        return self.get_gated_reasoning(obj)

    def get_gated_reasoning(self, obj) -> str:
        """
        Returns reasoning abstracted to the user's intelligence level.
        Raw reasoning is NEVER exposed directly via API.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return "This product may need your attention."

        from apps.engine.gating import IntelligenceGate
        gate    = IntelligenceGate()
        ctx     = gate.build_context(request.user, obj.product)
        return gate.abstract_reasoning(obj.reasoning, ctx.reasoning_depth)


class DecisionSimulationScenarioSerializer(serializers.Serializer):
    label = serializers.CharField()
    delay_days = serializers.IntegerField()
    projected_stock = serializers.FloatField()
    projected_stockout_date = serializers.DateField(allow_null=True)
    estimated_revenue_loss = serializers.FloatField()
    confidence = serializers.FloatField()


class DecisionSimulationSerializer(serializers.Serializer):
    available = serializers.BooleanField()
    recommended = DecisionSimulationScenarioSerializer(allow_null=True)
    alternatives = DecisionSimulationScenarioSerializer(many=True)
    reason = serializers.CharField(allow_blank=True, required=False)

# ── Dashboard serializers ──────────────────────────────────────────────────────

class DashboardSummarySerializer(serializers.Serializer):
    """
    Single-call aggregation of the full business state.
    Designed for the dashboard's initial load — one request, everything needed.
    """
    total_products              = serializers.IntegerField()
    products_needing_action     = serializers.IntegerField()
    products_low_confidence     = serializers.IntegerField()
    critical_alerts             = serializers.IntegerField()
    avg_confidence              = serializers.FloatField()

    # Tier info
    tier                        = serializers.CharField()
    is_pro                      = serializers.BooleanField()

    # Active decisions (PRO only — None for free tier)
    active_decisions            = DecisionLogSerializer(
        many=True, allow_null=True
    )
    top_priorities              = DecisionLogSerializer(many=True, allow_null=True)

    # Products needing immediate attention
    urgent_products             = ProductListSerializer(many=True)
    contextual_insights         = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )
    user_context                = serializers.DictField()
    journey_hint                = serializers.CharField(allow_blank=True)

    # System health signals
    last_learning_at            = serializers.DateTimeField(allow_null=True)
    stockouts_within_7d         = serializers.IntegerField()
    revenue_at_risk_total       = serializers.FloatField()
    stale_products_count        = serializers.IntegerField()
    actioned_decisions_14d      = serializers.IntegerField()
    ignored_decisions_14d       = serializers.IntegerField()
    managerial_brief            = serializers.DictField()
    managerial_signals          = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True,
    )
    usage_policy                = serializers.DictField()
    operating_assumption        = serializers.CharField(allow_blank=True)
    baseline_in_use             = serializers.BooleanField(required=False)
    demand_deficits             = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True,
        required=False,
    )


class ReorderRecordSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    decision_id = serializers.UUIDField(source="decision.id", read_only=True)

    class Meta:
        model = ReorderRecord
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "decision_id",
            "suggested_quantity",
            "suggested_date",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "product_name", "product_sku", "decision_id"]


class PortfolioSummarySerializer(serializers.Serializer):
    total_revenue_at_risk = serializers.FloatField()
    products_needing_action = serializers.IntegerField()
    top_decisions = DecisionLogSerializer(many=True)
    forecast_accuracy = serializers.FloatField()
    confidence_score = serializers.FloatField()
    overstock_capital = serializers.FloatField()


class BusinessHealthSummarySerializer(serializers.Serializer):
    estimated_monthly_revenue = serializers.FloatField()
    estimated_weekly_revenue = serializers.FloatField()
    potential_revenue_gap_weekly = serializers.FloatField()
    confidence_score = serializers.FloatField()


class BusinessHealthTopProductSerializer(serializers.Serializer):
    name = serializers.CharField()
    estimated_weekly_revenue = serializers.FloatField()


class BusinessHealthDemandGapSerializer(serializers.Serializer):
    name = serializers.CharField()
    expected_weekly_demand = serializers.FloatField()
    observed_weekly_demand = serializers.FloatField()
    gap_units = serializers.FloatField()
    gap_revenue = serializers.FloatField()
    confidence = serializers.FloatField()


class BusinessHealthReportSerializer(serializers.Serializer):
    summary = BusinessHealthSummarySerializer()
    top_products = BusinessHealthTopProductSerializer(many=True)
    demand_gaps = BusinessHealthDemandGapSerializer(many=True)
    insights = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    investor_summary = serializers.CharField()
