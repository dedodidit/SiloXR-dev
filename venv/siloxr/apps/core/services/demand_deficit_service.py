from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db.models import Prefetch
from django.db.utils import OperationalError
from django.utils import timezone

from apps.core.baselines import clean_source_text, normalize_industry, normalize_product_name
from apps.core.models import NigeriaBaselineProduct
from apps.inventory.models import BurnRate, InventoryEvent, Product


@dataclass
class ProductObservation:
    product: Product
    burn_rate: BurnRate | None
    observed_daily_demand: float
    recent_sale_count: int


class DemandDeficitService:
    NEGLIGIBLE_GAP = 0.25
    MAX_RESULTS = 3

    def analyze_product_deficits(self, user) -> list[dict[str, Any]]:
        country = clean_source_text(getattr(user, "country", "") or "").lower() or "nigeria"
        if country != "nigeria":
            return []

        industry = normalize_industry(getattr(user, "business_type", "") or "retail")
        try:
            baselines = list(
                NigeriaBaselineProduct.objects.filter(
                    country=country,
                    industry=industry,
                ).order_by("-avg_weekly_turnover")
            )
        except OperationalError:
            return []
        if not baselines:
            return []

        product_qs = Product.objects.filter(owner=user, is_active=True).prefetch_related(
            Prefetch("burn_rates", queryset=BurnRate.objects.order_by("-computed_at")),
            Prefetch("events", queryset=InventoryEvent.objects.order_by("-occurred_at")),
        )
        observed_index, exact_index = self._build_observation_index(product_qs)

        deficits: list[dict[str, Any]] = []
        for baseline in baselines:
            if baseline.avg_unit_price is None:
                continue

            expected_daily = round(float(baseline.avg_weekly_turnover) / 7.0, 4)
            observation = exact_index.get(self._exact_key(baseline.product_name))
            if observation is None:
                observation = observed_index.get(baseline.generic_category)
            observed_daily = round(observation.observed_daily_demand if observation else 0.0, 4)
            demand_gap = round(max(0.0, expected_daily - observed_daily), 4)
            if demand_gap <= self.NEGLIGIBLE_GAP:
                continue

            price = float(baseline.avg_unit_price)
            daily_revenue = round(demand_gap * price, 2)
            weekly_revenue = round(daily_revenue * 7.0, 2)

            causes = self._likely_causes(observation)
            confidence = self._confidence_for(observation)
            deficits.append(
                {
                    "product_name": baseline.product_name,
                    "category": baseline.category,
                    "generic_category": baseline.generic_category,
                    "cv_estimate": round(float(baseline.cv_estimate), 4),
                    "expected_daily_demand": expected_daily,
                    "observed_daily_demand": observed_daily,
                    "demand_gap": demand_gap,
                    "revenue_risk_daily": daily_revenue,
                    "revenue_risk_weekly": weekly_revenue,
                    "customers_lost_daily": round(demand_gap, 4),
                    "confidence": confidence,
                    "likely_causes": causes,
                    "explanation": self._build_explanation(
                        product_name=baseline.product_name,
                        expected_daily=expected_daily,
                        observed_daily=observed_daily,
                        demand_gap=demand_gap,
                        causes=causes,
                        daily_revenue=daily_revenue,
                        weekly_revenue=weekly_revenue,
                    ),
                    "impact_score": daily_revenue,
                }
            )

        deficits.sort(key=lambda item: item["impact_score"], reverse=True)
        trimmed = deficits[: self.MAX_RESULTS]
        for item in trimmed:
            item.pop("impact_score", None)
        return trimmed

    def _build_observation_index(self, products) -> tuple[dict[str, ProductObservation], dict[str, ProductObservation]]:
        seven_days_ago = timezone.now() - timedelta(days=7)
        observations: dict[str, ProductObservation] = {}
        exact_matches: dict[str, ProductObservation] = {}

        for product in products:
            generic_category = normalize_product_name(product.name, product.category)
            burn_rate = next(iter(product.burn_rates.all()), None)
            recent_sale_count = sum(
                1
                for event in product.events.all()
                if event.event_type == InventoryEvent.SALE and event.occurred_at >= seven_days_ago
            )
            observed_daily = float(burn_rate.burn_rate_per_day) if burn_rate else 0.0
            observation = ProductObservation(
                product=product,
                burn_rate=burn_rate,
                observed_daily_demand=observed_daily,
                recent_sale_count=recent_sale_count,
            )
            exact_matches[self._exact_key(product.name)] = observation
            current = observations.get(generic_category)
            if current is None or observed_daily > current.observed_daily_demand:
                observations[generic_category] = observation
        return observations, exact_matches

    def _exact_key(self, value: str) -> str:
        return clean_source_text(value).lower()

    def _likely_causes(self, observation: ProductObservation | None) -> list[str]:
        if observation is None:
            return ["product not currently tracked"]

        causes: list[str] = []
        product = observation.product
        if product.estimated_quantity <= max(float(product.reorder_point or 0), observation.observed_daily_demand * 2.0):
            causes.append("likely understocked")
        if observation.burn_rate is None or observation.burn_rate.sample_event_count < 4 or observation.recent_sale_count == 0:
            causes.append("sales may not be fully recorded")
        return causes[:2] or ["sales may not be fully recorded"]

    def _confidence_for(self, observation: ProductObservation | None) -> float:
        if observation is None:
            return 0.45

        burn_rate = observation.burn_rate
        if burn_rate is None:
            return 0.55

        event_strength = min(float(burn_rate.sample_event_count) / 10.0, 1.0)
        recent_signal = 1.0 if observation.recent_sale_count > 0 else 0.6
        confidence = 0.5 + (float(burn_rate.confidence_score) * 0.2) + (event_strength * 0.1) + ((recent_signal - 0.6) * 0.125)
        return round(min(0.85, max(0.4, confidence)), 2)

    def _build_explanation(
        self,
        *,
        product_name: str,
        expected_daily: float,
        observed_daily: float,
        demand_gap: float,
        causes: list[str],
        daily_revenue: float,
        weekly_revenue: float,
    ) -> str:
        cause_lines = "\n".join(f"• {cause}" for cause in causes[:2])
        return (
            f"High-demand item likely underperforming:\n\n"
            f"{product_name}\n\n"
            f"Similar businesses typically sell ~{expected_daily:.2f} units/day\n\n"
            f"We are currently observing ~{observed_daily:.2f} units/day\n\n"
            f"→ Gap: ~{demand_gap:.2f} sales/day\n\n"
            f"This may be due to:\n"
            f"{cause_lines}\n\n"
            f"Estimated impact:\n"
            f"≈ ₦{daily_revenue:,.2f} per day (≈ ₦{weekly_revenue:,.2f} per week)"
        )


def analyze_product_deficits(user) -> list[dict[str, Any]]:
    return DemandDeficitService().analyze_product_deficits(user)
