from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.utils import timezone

from apps.core.baselines import NigeriaBaselineService
from apps.inventory.models import BurnRate, Product


def build_business_health_report(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Pure deterministic report builder for raw business demand inputs.

    Example:
        payload = {
            "business_id": "biz_123",
            "products": [
                {
                    "name": "Coca-Cola 50cl PET",
                    "category": "beverages",
                    "price": 300,
                    "expected_weekly_demand": 70,
                    "observed_weekly_demand": 49,
                    "confidence": 0.74,
                }
            ],
            "currency": "NGN",
        }
        report = build_business_health_report(payload)
    """

    currency = str(payload.get("currency") or "NGN").upper()
    normalized_products = [_normalize_product(item) for item in payload.get("products") or []]

    weekly_revenue = round(
        sum(item["price"] * item["observed_weekly_demand"] for item in normalized_products),
        2,
    )
    monthly_revenue = round(weekly_revenue * 4, 2)

    demand_gaps = []
    for item in normalized_products:
        gap_units = round(max(item["expected_weekly_demand"] - item["observed_weekly_demand"], 0.0), 4)
        if gap_units <= 0:
            continue
        gap_revenue = round(gap_units * item["price"], 2)
        demand_gaps.append(
            {
                "name": item["name"],
                "expected_weekly_demand": round(item["expected_weekly_demand"], 4),
                "observed_weekly_demand": round(item["observed_weekly_demand"], 4),
                "gap_units": gap_units,
                "gap_revenue": gap_revenue,
                "confidence": round(item["confidence"], 4),
            }
        )

    demand_gaps.sort(key=lambda gap: (gap["gap_revenue"], gap["gap_units"]), reverse=True)
    potential_revenue_gap_weekly = round(sum(item["gap_revenue"] for item in demand_gaps), 2)
    confidence_score = _weighted_confidence(normalized_products)

    top_products = [
        {
            "name": item["name"],
            "estimated_weekly_revenue": round(item["price"] * item["observed_weekly_demand"], 2),
        }
        for item in sorted(
            normalized_products,
            key=lambda product: (product["price"] * product["observed_weekly_demand"], product["observed_weekly_demand"]),
            reverse=True,
        )[:5]
        if (item["price"] * item["observed_weekly_demand"]) > 0
    ]

    insights = _build_insights(
        currency=currency,
        weekly_revenue=weekly_revenue,
        potential_revenue_gap_weekly=potential_revenue_gap_weekly,
        top_products=top_products,
        demand_gaps=demand_gaps,
        products=normalized_products,
    )
    investor_summary = _build_investor_summary(
        currency=currency,
        monthly_revenue=monthly_revenue,
        weekly_revenue=weekly_revenue,
        potential_revenue_gap_weekly=potential_revenue_gap_weekly,
        top_products=top_products,
        confidence_score=confidence_score,
        demand_gaps=demand_gaps,
    )

    return {
        "summary": {
            "estimated_monthly_revenue": monthly_revenue,
            "estimated_weekly_revenue": weekly_revenue,
            "potential_revenue_gap_weekly": potential_revenue_gap_weekly,
            "confidence_score": confidence_score,
        },
        "top_products": top_products,
        "demand_gaps": demand_gaps,
        "insights": insights,
        "investor_summary": investor_summary,
    }


@dataclass
class BusinessHealthInputProduct:
    name: str
    category: str
    price: float
    expected_weekly_demand: float
    observed_weekly_demand: float
    confidence: float


class BusinessHealthReportService:
    """
    Production-facing report service for dashboard, PDF export, and partner views.
    """

    def __init__(self, *, baseline_service: NigeriaBaselineService | None = None):
        self.baseline_service = baseline_service or NigeriaBaselineService()

    def report_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return build_business_health_report(payload)

    def build_payload_for_user(self, user, *, currency: str = "NGN") -> dict[str, Any]:
        products = (
            Product.objects.filter(owner=user, is_active=True)
            .prefetch_related("burn_rates")
            .order_by("name")
        )

        payload_products: list[dict[str, Any]] = []
        for product in products:
            burn_rate = next(iter(product.burn_rates.all()), None)
            observed_weekly = self._observed_weekly_demand(product, burn_rate)
            expected_weekly = self._expected_weekly_demand(product, observed_weekly)
            payload_products.append(
                {
                    "name": product.name,
                    "category": product.category or "",
                    "price": float(product.selling_price or 0.0),
                    "expected_weekly_demand": expected_weekly,
                    "observed_weekly_demand": observed_weekly,
                    "confidence": float(product.confidence_score or 0.0),
                }
            )

        return {
            "business_id": str(user.id),
            "products": payload_products,
            "currency": currency,
        }

    def report_for_user(self, user, *, currency: str = "NGN") -> dict[str, Any]:
        return self.report_from_payload(self.build_payload_for_user(user, currency=currency))

    def build_pdf_context(self, user, *, period_end: date | None = None, currency: str = "NGN") -> dict[str, Any]:
        report = self.report_for_user(user, currency=currency)
        end = period_end or timezone.localdate()
        start = end.replace(day=1)
        return {
            "business_id": str(user.id),
            "business_name": getattr(user, "business_name", "") or getattr(user, "username", "") or str(user.id),
            "currency": currency.upper(),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "report": report,
        }

    def build_monthly_dispatch_payload(
        self,
        user,
        *,
        period_end: date | None = None,
        currency: str = "NGN",
    ) -> dict[str, Any]:
        pdf_context = self.build_pdf_context(user, period_end=period_end, currency=currency)
        return {
            "channel": "email",
            "template": "business_health_monthly_report",
            "pdf_context": pdf_context,
            "report": pdf_context["report"],
        }

    def build_partner_snapshot(self, user, *, currency: str = "NGN") -> dict[str, Any]:
        report = self.report_for_user(user, currency=currency)
        summary = report["summary"]
        return {
            "business_id": str(user.id),
            "currency": currency.upper(),
            "estimated_monthly_revenue": summary["estimated_monthly_revenue"],
            "potential_revenue_gap_weekly": summary["potential_revenue_gap_weekly"],
            "confidence_score": summary["confidence_score"],
            "top_products": report["top_products"][:3],
        }

    def _observed_weekly_demand(self, product: Product, burn_rate: BurnRate | None) -> float:
        if burn_rate is None:
            return 0.0
        return round(max(float(burn_rate.burn_rate_per_day or 0.0) * 7.0, 0.0), 4)

    def _expected_weekly_demand(self, product: Product, observed_weekly: float) -> float:
        baseline = self.baseline_service.for_product(product)
        if baseline and baseline.get("avg_weekly_turnover") is not None:
            return round(max(float(baseline["avg_weekly_turnover"]), observed_weekly, 0.0), 4)
        return round(max(observed_weekly, 0.0), 4)


def _normalize_product(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or "Unnamed product").strip() or "Unnamed product",
        "category": str(item.get("category") or "").strip(),
        "price": _safe_non_negative_number(item.get("price")),
        "expected_weekly_demand": _safe_non_negative_number(item.get("expected_weekly_demand")),
        "observed_weekly_demand": _safe_non_negative_number(item.get("observed_weekly_demand")),
        "confidence": _clamp(_safe_non_negative_number(item.get("confidence")), 0.0, 1.0),
    }


def _safe_non_negative_number(value: Any) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(number, 0.0)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _weighted_confidence(products: list[dict[str, Any]]) -> float:
    if not products:
        return 0.0

    weighted_total = 0.0
    weight_sum = 0.0
    for item in products:
        weight = max(
            item["price"] * max(item["expected_weekly_demand"], item["observed_weekly_demand"]),
            max(item["expected_weekly_demand"], item["observed_weekly_demand"], 1.0),
        )
        weighted_total += item["confidence"] * weight
        weight_sum += weight

    if weight_sum <= 0:
        return 0.0
    return round(weighted_total / weight_sum, 4)


def _build_insights(
    *,
    currency: str,
    weekly_revenue: float,
    potential_revenue_gap_weekly: float,
    top_products: list[dict[str, Any]],
    demand_gaps: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> list[str]:
    insights: list[str] = []

    if demand_gaps:
        top_gap = demand_gaps[0]
        insights.append(
            f"You may be missing {_format_currency(top_gap['gap_revenue'], currency)}/week from {top_gap['name']}."
        )
        insights.append(
            f"Demand for {top_gap['name']} exceeds current observed sales by about {round(top_gap['gap_units'], 1)} units/week."
        )

        top_three_gap_value = sum(item["gap_revenue"] for item in demand_gaps[:3])
        if weekly_revenue > 0 and top_three_gap_value > 0:
            uplift_pct = round((top_three_gap_value / weekly_revenue) * 100)
            insights.append(
                f"Closing the top 3 gaps could increase weekly revenue by about {uplift_pct}%."
            )
        elif top_three_gap_value > 0:
            insights.append(
                f"Closing the top 3 gaps could unlock {_format_currency(top_three_gap_value, currency)}/week in new revenue."
            )

    if top_products:
        driver_names = ", ".join(item["name"] for item in top_products[:3])
        insights.append(f"Current revenue is led by {driver_names}.")

    low_confidence_products = [item for item in products if item["confidence"] < 0.45]
    if low_confidence_products:
        names = ", ".join(item["name"] for item in low_confidence_products[:2])
        insights.append(
            f"Signals for {names} are lower-confidence, so stronger event capture would sharpen this report."
        )

    if not insights:
        insights.append("No demand gap is currently visible from the available operating data.")

    return insights[:5]


def _build_investor_summary(
    *,
    currency: str,
    monthly_revenue: float,
    weekly_revenue: float,
    potential_revenue_gap_weekly: float,
    top_products: list[dict[str, Any]],
    confidence_score: float,
    demand_gaps: list[dict[str, Any]],
) -> str:
    top_names = ", ".join(item["name"] for item in top_products[:3]) or "current operating lines"
    if monthly_revenue <= 0 and not demand_gaps:
        return (
            "This business does not yet have enough recorded operating activity to estimate recurring revenue with confidence. "
            "More stock counts, sales events, and demand observations will improve the investor picture."
        )

    leakage_clause = (
        f"Current analysis suggests a weekly revenue leakage of {_format_currency(potential_revenue_gap_weekly, currency)} due to unmet demand. "
        if potential_revenue_gap_weekly > 0
        else "Current analysis does not show a material weekly revenue leakage from unmet demand. "
    )
    return (
        f"This business processes approximately {_format_currency(monthly_revenue, currency)} per month "
        f"({_format_currency(weekly_revenue, currency)} per week), with key revenue drivers in {top_names}. "
        f"{leakage_clause}"
        f"The confidence level on this view is {round(confidence_score * 100)}%, and addressing the most visible demand gaps presents "
        f"a clear opportunity for revenue growth without significant expansion."
    )


def _format_currency(value: float, currency: str) -> str:
    symbol_map = {
        "NGN": "₦",
        "N": "₦",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
    }
    symbol = symbol_map.get(currency.upper(), f"{currency.upper()} ")
    return f"{symbol}{round(float(value or 0.0), 2):,.2f}"
