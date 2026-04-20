from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from math import ceil, inf
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from apps.inventory.models import InventoryEvent, Product


COMPARISON_WINDOW_DAYS = 7
DEAD_STOCK_DAYS = 10
STOCKOUT_THRESHOLD_DAYS = 3
DROP_THRESHOLD = 0.5


CURRENCY_SYMBOLS = {
    "NGN": "₦",
    "USD": "$",
    "GHS": "GH₵",
    "KES": "KSh",
    "INR": "₹",
    "ZAR": "R",
    "AED": "د.إ",
    "GBP": "£",
    "CAD": "C$",
}


@dataclass
class ProductInsightResult:
    product_id: str
    product_name: str
    notification_type: str
    severity: str
    message: str
    should_notify: bool
    reference_id: str
    title: str
    confidence: float
    burn_rate_per_day: float = 0.0
    days_to_stockout: float | None = None
    observed_weekly_demand: float = 0.0
    expected_weekly_demand: float = 0.0
    potential_revenue_loss_weekly: float = 0.0
    recommended_action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _currency_symbol(currency: str | None) -> str:
    code = (currency or "").strip().upper()
    return CURRENCY_SYMBOLS.get(code, code or "$")


def _money_text(amount: float, currency: str | None) -> str:
    symbol = _currency_symbol(currency)
    if symbol == currency and symbol not in {"₦", "$", "GH₵", "KSh", "₹", "R", "د.إ", "£", "C$"}:
        return f"{amount:,.0f} {symbol}"
    return f"{symbol}{amount:,.0f}"


def _product_stock(product: Product) -> float:
    current_stock = getattr(product, "current_stock", None)
    if current_stock is not None:
        return float(current_stock or 0.0)
    estimated = float(getattr(product, "estimated_quantity", 0.0) or 0.0)
    verified = float(getattr(product, "last_verified_quantity", 0.0) or 0.0)
    return estimated if estimated > 0 else verified


def _sale_totals(product: Product, start, end=None) -> float:
    qs = InventoryEvent.objects.filter(
        product=product,
        event_type=InventoryEvent.SALE,
        occurred_at__gte=start,
    )
    if end is not None:
        qs = qs.filter(occurred_at__lt=end)
    total = qs.aggregate(total=Sum("quantity")).get("total") or 0
    return float(total or 0.0)


def _latest_sale_at(product: Product):
    return (
        InventoryEvent.objects.filter(
            product=product,
            event_type=InventoryEvent.SALE,
        )
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )


def _base_reference_id(product: Product) -> str:
    return f"product:{product.id}"


def _insight_title(notification_type: str, product_name: str) -> str:
    labels = {
        "stockout_risk": "Stockout risk",
        "dead_stock": "Dead stock",
        "drop": "Demand drop",
    }
    label = labels.get(notification_type, "Inventory insight")
    return f"{label}: {product_name}"


def generate_product_insight(product_id) -> ProductInsightResult:
    """
    Generate one actionable insight for a product.
    Returns a non-notifying result when the product is currently healthy.
    """
    product = product_id if isinstance(product_id, Product) else Product.objects.select_related("owner").get(id=product_id)
    now = timezone.now()
    currency = getattr(product.owner, "currency", "") or "USD"
    current_stock = max(0.0, _product_stock(product))

    recent_window_start = now - timedelta(days=COMPARISON_WINDOW_DAYS)
    previous_window_start = now - timedelta(days=COMPARISON_WINDOW_DAYS * 2)
    recent_sales = _sale_totals(product, recent_window_start)
    previous_sales = _sale_totals(product, previous_window_start, recent_window_start)
    recent_daily = recent_sales / float(COMPARISON_WINDOW_DAYS)
    previous_daily = previous_sales / float(COMPARISON_WINDOW_DAYS)
    burn_rate = recent_daily
    expected_weekly = recent_daily * 7.0
    observed_weekly = recent_daily * 7.0
    days_to_stockout = (current_stock / burn_rate) if burn_rate > 0 else None
    latest_sale_at = _latest_sale_at(product)
    days_since_sale = None
    if latest_sale_at is not None:
        days_since_sale = max(0, (now - latest_sale_at).days)
    else:
        days_since_sale = max(0, (now - getattr(product, "created_at", now)).days)

    price = float(getattr(product, "selling_price", None) or 0.0)
    cost = float(getattr(product, "cost_price", None) or 0.0)

    if burn_rate > 0 and days_to_stockout is not None and days_to_stockout <= STOCKOUT_THRESHOLD_DAYS:
        shortfall_units = max(0.0, expected_weekly - current_stock)
        revenue_loss = shortfall_units * price if price > 0 else 0.0
        restock_units = max(
            int(ceil(burn_rate * 7.0)),
            int(getattr(product, "reorder_quantity", 0) or 0),
            int(ceil(burn_rate * 3.0)),
        )
        if revenue_loss > 0:
            message = (
                f"You may run out of {product.name} in about {max(1, round(days_to_stockout))} days "
                f"→ potential loss {_money_text(revenue_loss, currency)} this week. "
                f"Restock about {restock_units} units."
            )
        else:
            message = (
                f"You may run out of {product.name} in about {max(1, round(days_to_stockout))} days. "
                f"Restock about {restock_units} units."
            )
        return ProductInsightResult(
            product_id=str(product.id),
            product_name=product.name,
            notification_type="stockout_risk",
            severity="critical" if days_to_stockout <= 1 else "high",
            message=message,
            should_notify=True,
            reference_id=_base_reference_id(product),
            title=_insight_title("stockout_risk", product.name),
            confidence=min(0.95, max(0.55, getattr(product, "confidence_score", 0.5) or 0.5)),
            burn_rate_per_day=burn_rate,
            days_to_stockout=days_to_stockout,
            observed_weekly_demand=observed_weekly,
            expected_weekly_demand=expected_weekly,
            potential_revenue_loss_weekly=revenue_loss,
            recommended_action=f"Restock {restock_units} units now.",
            metadata={
                "current_stock": current_stock,
                "price": price,
                "currency": currency,
                "latest_sale_at": latest_sale_at.isoformat() if latest_sale_at else None,
            },
        )

    if days_since_sale is not None and days_since_sale >= DEAD_STOCK_DAYS and current_stock > 0:
        capital_tied = current_stock * cost if cost > 0 else current_stock * price
        if capital_tied > 0:
            message = (
                f"{product.name} has not moved in {days_since_sale} days → about "
                f"{_money_text(capital_tied, currency)} may be tied up in stock. "
                f"Review pricing or clear excess units."
            )
        else:
            message = (
                f"{product.name} has not moved in {days_since_sale} days. "
                f"Review pricing or clear excess units."
            )
        return ProductInsightResult(
            product_id=str(product.id),
            product_name=product.name,
            notification_type="dead_stock",
            severity="medium" if days_since_sale < DEAD_STOCK_DAYS + 7 else "high",
            message=message,
            should_notify=True,
            reference_id=_base_reference_id(product),
            title=_insight_title("dead_stock", product.name),
            confidence=min(0.8, max(0.45, getattr(product, "confidence_score", 0.5) or 0.5)),
            burn_rate_per_day=burn_rate,
            days_to_stockout=days_to_stockout,
            observed_weekly_demand=observed_weekly,
            expected_weekly_demand=expected_weekly,
            potential_revenue_loss_weekly=capital_tied,
            recommended_action="Review pricing, placement, or reorder plan.",
            metadata={
                "current_stock": current_stock,
                "latest_sale_at": latest_sale_at.isoformat() if latest_sale_at else None,
            },
        )

    if previous_daily > 0 and recent_daily <= previous_daily * (1.0 - DROP_THRESHOLD):
        drop_pct = max(0.0, (previous_daily - recent_daily) / previous_daily)
        revenue_loss = max(0.0, (previous_daily - recent_daily) * 7.0 * price) if price > 0 else 0.0
        if revenue_loss > 0:
            message = (
                f"Sales for {product.name} fell by about {round(drop_pct * 100):.0f}% vs the previous week "
                f"→ potential loss {_money_text(revenue_loss, currency)} weekly. "
                f"Check stock flow and recent demand shifts."
            )
        else:
            message = (
                f"Sales for {product.name} fell by about {round(drop_pct * 100):.0f}% vs the previous week. "
                f"Check stock flow and recent demand shifts."
            )
        return ProductInsightResult(
            product_id=str(product.id),
            product_name=product.name,
            notification_type="drop",
            severity="high" if drop_pct >= 0.65 else "medium",
            message=message,
            should_notify=True,
            reference_id=_base_reference_id(product),
            title=_insight_title("drop", product.name),
            confidence=min(0.85, max(0.5, getattr(product, "confidence_score", 0.5) or 0.5)),
            burn_rate_per_day=burn_rate,
            days_to_stockout=days_to_stockout,
            observed_weekly_demand=observed_weekly,
            expected_weekly_demand=expected_weekly,
            potential_revenue_loss_weekly=revenue_loss,
            recommended_action="Review recent demand and product availability.",
            metadata={
                "previous_week_units": previous_sales,
                "recent_week_units": recent_sales,
                "drop_pct": drop_pct,
                "current_stock": current_stock,
            },
        )

    return ProductInsightResult(
        product_id=str(product.id),
        product_name=product.name,
        notification_type="",
        severity="low",
        message=f"{product.name} is being tracked. Activity is currently steady.",
        should_notify=False,
        reference_id=_base_reference_id(product),
        title=_insight_title("generic", product.name),
        confidence=min(0.7, max(0.4, getattr(product, "confidence_score", 0.5) or 0.5)),
        burn_rate_per_day=burn_rate,
        days_to_stockout=days_to_stockout if days_to_stockout != inf else None,
        observed_weekly_demand=observed_weekly,
        expected_weekly_demand=expected_weekly,
        potential_revenue_loss_weekly=0.0,
        recommended_action="Continue logging sales and stock updates.",
        metadata={
            "current_stock": current_stock,
            "recent_sales": recent_sales,
            "previous_sales": previous_sales,
            "currency": currency,
        },
    )
