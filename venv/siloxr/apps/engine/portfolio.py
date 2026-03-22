from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Avg, Sum
from django.utils import timezone

from apps.inventory.models import DecisionLog, ForecastSnapshot, Product
from apps.engine.priorities import get_top_priorities


@dataclass
class PortfolioSummary:
    total_revenue_at_risk: float
    products_needing_action: int
    top_decisions: list[DecisionLog]
    forecast_accuracy: float
    confidence_score: float
    overstock_capital: float


class PortfolioService:
    ACCURACY_WINDOW_DAYS = 30

    def summary_for_user(self, user) -> PortfolioSummary:
        now = timezone.now()
        active_decisions = list(
            DecisionLog.objects.filter(
                product__owner=user,
                expires_at__gt=now,
                is_acknowledged=False,
                priority_score__gt=0,
            )
            .exclude(
                status__in=[DecisionLog.STATUS_ACTED, DecisionLog.STATUS_IGNORED]
            )
            .exclude(action=DecisionLog.HOLD)
            .select_related("product")
            .order_by("-priority_score", "-estimated_revenue_loss")
        )

        products = Product.objects.filter(owner=user, is_active=True)
        total_revenue_at_risk = round(
            sum(float(d.estimated_revenue_loss or 0.0) for d in active_decisions),
            2,
        )
        products_needing_action = len({str(d.product_id) for d in active_decisions})
        confidence_score = round(
            float(products.aggregate(avg=Avg("confidence_score")).get("avg") or 0.0),
            4,
        )

        overstock_capital = 0.0
        for product in products:
            if not product.selling_price:
                continue
            surplus_qty = max(0.0, float(product.estimated_quantity or 0.0) - float(product.reorder_point or 0.0))
            if surplus_qty <= 0:
                continue
            overstock_capital += surplus_qty * float(product.selling_price)

        forecast_accuracy = self._forecast_accuracy(user)

        return PortfolioSummary(
            total_revenue_at_risk=total_revenue_at_risk,
            products_needing_action=products_needing_action,
            top_decisions=get_top_priorities(str(user.id), limit=5),
            forecast_accuracy=forecast_accuracy,
            confidence_score=confidence_score,
            overstock_capital=round(overstock_capital, 2),
        )

    def _forecast_accuracy(self, user) -> float:
        resolved = list(
            ForecastSnapshot.objects.filter(
                product__owner=user,
                actual_quantity__isnull=False,
            )
            .exclude(actual_quantity=0)
            .order_by("-forecast_date")[:60]
        )
        if not resolved:
            return 0.0

        errors = []
        for snap in resolved:
            if snap.actual_quantity is None or snap.actual_quantity <= 0:
                continue
            abs_pct_error = abs(float(snap.forecast_error or 0.0)) / max(float(snap.actual_quantity), 1.0)
            errors.append(abs_pct_error)

        if not errors:
            return 0.0

        accuracy = max(0.0, 1.0 - (sum(errors) / len(errors)))
        return round(min(1.0, accuracy), 4)
