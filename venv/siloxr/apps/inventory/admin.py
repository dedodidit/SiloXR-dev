# backend/apps/inventory/admin.py

from django.contrib import admin
from .models import Product, InventoryEvent, BurnRate, ForecastSnapshot, DecisionLog


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "sku", "last_verified_quantity", "estimated_quantity",
        "confidence_score", "needs_verification", "is_active",
    )
    list_filter = ("is_active", "category", "owner")
    search_fields = ("name", "sku")
    readonly_fields = (
        "id", "created_at", "updated_at",
        "last_verified_at", "quantity_gap",
    )


@admin.register(InventoryEvent)
class InventoryEventAdmin(admin.ModelAdmin):
    list_display = (
        "product", "event_type", "quantity", "verified_quantity",
        "occurred_at", "is_offline_event", "recorded_by",
    )
    list_filter = ("event_type", "is_offline_event")
    search_fields = ("product__sku", "product__name", "client_event_id")
    readonly_fields = ("id", "created_at", "signed_quantity")


@admin.register(BurnRate)
class BurnRateAdmin(admin.ModelAdmin):
    list_display = (
        "product", "burn_rate_per_day", "burn_rate_std_dev",
        "confidence_score", "sample_days", "computed_at",
    )
    readonly_fields = ("id", "computed_at", "days_remaining")


@admin.register(ForecastSnapshot)
class ForecastSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "product", "forecast_date", "predicted_quantity",
        "lower_bound", "upper_bound", "confidence_score",
        "actual_quantity", "forecast_error",
    )
    readonly_fields = ("id", "created_at", "is_resolvable")


@admin.register(DecisionLog)
class DecisionLogAdmin(admin.ModelAdmin):
    list_display = (
        "product", "action", "severity", "confidence_score",
        "is_acknowledged", "is_active", "created_at",
    )
    list_filter = ("action", "is_acknowledged")
    readonly_fields = ("id", "created_at", "severity", "is_expired", "is_active")