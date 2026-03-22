from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import NigeriaBaselineProduct
from apps.core.services.demand_deficit_service import analyze_product_deficits
from apps.inventory.models import BurnRate, InventoryEvent, Product


def make_user(username: str = "manager"):
    return get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="Password123!",
        business_type="retail",
    )


def make_baseline(
    *,
    product_name: str,
    category: str,
    generic_category: str,
    avg_weekly_turnover: float,
    avg_unit_price: float | None,
    industry: str = "retail",
):
    cv_estimate = 0.2
    return NigeriaBaselineProduct.objects.create(
        country="nigeria",
        industry=industry,
        category=category,
        generic_category=generic_category,
        product_name=product_name,
        unit_type="Case",
        weekly_turnover_low=avg_weekly_turnover - 7.0,
        weekly_turnover_high=avg_weekly_turnover + 7.0,
        avg_weekly_turnover=avg_weekly_turnover,
        demand_std=round(avg_weekly_turnover * cv_estimate, 4),
        daily_demand=round(avg_weekly_turnover / 7.0, 4),
        avg_unit_price=avg_unit_price,
        cv_estimate=cv_estimate,
        lead_time_days=2,
        source="test_fixture",
    )


def make_product(user, *, name: str, category: str, estimated_quantity: float = 20.0, reorder_point: int = 5):
    return Product.objects.create(
        owner=user,
        name=name,
        sku=f"sku-{name.lower().replace(' ', '-')}",
        category=category,
        estimated_quantity=estimated_quantity,
        reorder_point=reorder_point,
        confidence_score=0.6,
        is_active=True,
    )


def make_burn_rate(product, *, burn_rate_per_day: float, sample_event_count: int, confidence_score: float = 0.7):
    return BurnRate.objects.create(
        product=product,
        burn_rate_per_day=burn_rate_per_day,
        burn_rate_std_dev=1.0,
        sample_event_count=sample_event_count,
        confidence_score=confidence_score,
        window_days=30,
    )


def make_sale(product, user, *, quantity: float = 1.0, days_ago: int = 1):
    return InventoryEvent.objects.create(
        product=product,
        recorded_by=user,
        event_type=InventoryEvent.SALE,
        quantity=quantity,
        occurred_at=timezone.now() - timedelta(days=days_ago),
    )


@pytest.mark.django_db
def test_no_products_returns_baseline_only_deficits():
    user = make_user("baseline_only")
    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=70.0,
        avg_unit_price=100.0,
    )
    make_baseline(
        product_name="Sliced White Bread",
        category="bakery",
        generic_category="bread",
        avg_weekly_turnover=35.0,
        avg_unit_price=220.0,
    )

    deficits = analyze_product_deficits(user)

    assert len(deficits) == 2
    assert deficits[0]["product_name"] == "Sliced White Bread"
    assert deficits[0]["expected_daily_demand"] == 5.0
    assert deficits[0]["observed_daily_demand"] == 0.0
    assert deficits[0]["demand_gap"] == 5.0
    assert deficits[0]["revenue_risk_daily"] == 1100.0
    assert deficits[0]["revenue_risk_weekly"] == 7700.0
    assert deficits[0]["customers_lost_daily"] == 5.0
    assert deficits[0]["confidence"] == 0.45
    assert deficits[0]["likely_causes"] == ["product not currently tracked"]


@pytest.mark.django_db
def test_partial_products_return_mixed_deficits():
    user = make_user("partial")
    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=70.0,
        avg_unit_price=100.0,
    )
    make_baseline(
        product_name="Sliced White Bread",
        category="bakery",
        generic_category="bread",
        avg_weekly_turnover=35.0,
        avg_unit_price=220.0,
    )
    coke = make_product(user, name="Coca-Cola 50cl PET", category="beverages", estimated_quantity=3.0, reorder_point=5)
    make_sale(coke, user, quantity=2.0, days_ago=1)
    make_burn_rate(coke, burn_rate_per_day=6.0, sample_event_count=6, confidence_score=0.7)

    deficits = analyze_product_deficits(user)

    assert len(deficits) == 2
    assert deficits[0]["product_name"] == "Sliced White Bread"
    assert deficits[0]["revenue_risk_daily"] == 1100.0
    assert deficits[1]["product_name"] == "Coca-Cola 50cl PET"
    assert deficits[1]["expected_daily_demand"] == 10.0
    assert deficits[1]["observed_daily_demand"] == 6.0
    assert deficits[1]["demand_gap"] == 4.0
    assert deficits[1]["revenue_risk_daily"] == 400.0
    assert deficits[1]["revenue_risk_weekly"] == 2800.0
    assert deficits[1]["likely_causes"] == ["likely understocked"]
    assert deficits[1]["confidence"] == 0.75


@pytest.mark.django_db
def test_full_coverage_with_sufficient_observed_demand_returns_no_deficits():
    user = make_user("full")
    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=70.0,
        avg_unit_price=100.0,
    )
    coke = make_product(user, name="Coca-Cola 50cl PET", category="beverages", estimated_quantity=40.0, reorder_point=5)
    make_sale(coke, user, quantity=2.0, days_ago=1)
    make_burn_rate(coke, burn_rate_per_day=10.0, sample_event_count=8, confidence_score=0.8)

    deficits = analyze_product_deficits(user)

    assert deficits == []


@pytest.mark.django_db
def test_deficits_rank_by_daily_revenue_impact():
    user = make_user("ranking")
    make_baseline(
        product_name="Product A",
        category="bakery",
        generic_category="bread",
        avg_weekly_turnover=70.0,
        avg_unit_price=100.0,
    )
    make_baseline(
        product_name="Product B",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=35.0,
        avg_unit_price=300.0,
    )
    product_b = make_product(user, name="Coca-Cola 50cl PET", category="beverages", estimated_quantity=30.0, reorder_point=4)
    make_sale(product_b, user, quantity=1.0, days_ago=1)
    make_burn_rate(product_b, burn_rate_per_day=1.0, sample_event_count=5, confidence_score=0.6)

    deficits = analyze_product_deficits(user)

    assert [item["product_name"] for item in deficits] == ["Product B", "Product A"]
    assert deficits[0]["revenue_risk_daily"] == 1200.0
    assert deficits[1]["revenue_risk_daily"] == 1000.0


@pytest.mark.django_db
def test_cause_detection_returns_understocked_and_low_recording():
    user = make_user("causes")
    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=70.0,
        avg_unit_price=100.0,
    )
    coke = make_product(user, name="Coca-Cola 50cl PET", category="beverages", estimated_quantity=1.0, reorder_point=5)
    make_burn_rate(coke, burn_rate_per_day=3.0, sample_event_count=2, confidence_score=0.55)

    deficits = analyze_product_deficits(user)

    assert len(deficits) == 1
    assert deficits[0]["likely_causes"] == ["likely understocked", "sales may not be fully recorded"]
    assert deficits[0]["revenue_risk_daily"] == 700.0
    assert "Gap: ~7.00 sales/day" in deficits[0]["explanation"]


@pytest.mark.django_db
def test_missing_price_and_missing_burn_rate_do_not_crash():
    user = make_user("missing")
    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=70.0,
        avg_unit_price=None,
    )
    make_product(user, name="Coca-Cola 50cl PET", category="beverages", estimated_quantity=10.0, reorder_point=5)

    deficits = analyze_product_deficits(user)

    assert deficits == []
