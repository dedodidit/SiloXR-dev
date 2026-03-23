import pytest
from django.contrib.auth import get_user_model

from apps.core.models import NigeriaBaselineProduct
from apps.engine.business_health import BusinessHealthReportService, build_business_health_report
from apps.inventory.models import BurnRate, Product


def make_user(username: str = "health-user"):
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
):
    return NigeriaBaselineProduct.objects.create(
        country="nigeria",
        industry="retail",
        category=category,
        generic_category=generic_category,
        product_name=product_name,
        unit_type="unit",
        weekly_turnover_low=max(avg_weekly_turnover - 5.0, 0.0),
        weekly_turnover_high=avg_weekly_turnover + 5.0,
        avg_weekly_turnover=avg_weekly_turnover,
        demand_std=4.0,
        daily_demand=round(avg_weekly_turnover / 7.0, 4),
        avg_unit_price=avg_unit_price,
        cv_estimate=0.22,
        lead_time_days=2,
        source="test_fixture",
    )


def make_product(user, *, name: str, category: str, selling_price: float | None, confidence_score: float = 0.7):
    return Product.objects.create(
        owner=user,
        name=name,
        sku=f"sku-{name.lower().replace(' ', '-')}",
        category=category,
        selling_price=selling_price,
        estimated_quantity=20.0,
        reorder_point=5,
        confidence_score=confidence_score,
        is_active=True,
    )


def make_burn_rate(product, *, burn_rate_per_day: float, confidence_score: float = 0.7):
    return BurnRate.objects.create(
        product=product,
        burn_rate_per_day=burn_rate_per_day,
        burn_rate_std_dev=1.0,
        sample_event_count=8,
        confidence_score=confidence_score,
        window_days=30,
    )


def test_build_business_health_report_handles_empty_payload():
    report = build_business_health_report(
        {
            "business_id": "biz-empty",
            "products": [],
            "currency": "NGN",
        }
    )

    assert report["summary"]["estimated_weekly_revenue"] == 0.0
    assert report["summary"]["estimated_monthly_revenue"] == 0.0
    assert report["summary"]["potential_revenue_gap_weekly"] == 0.0
    assert report["summary"]["confidence_score"] == 0.0
    assert report["top_products"] == []
    assert report["demand_gaps"] == []
    assert report["insights"] == ["No demand gap is currently visible from the available operating data."]


def test_build_business_health_report_ignores_negative_gaps_and_missing_price():
    report = build_business_health_report(
        {
            "business_id": "biz-raw",
            "currency": "NGN",
            "products": [
                {
                    "name": "Bread",
                    "category": "bakery",
                    "price": 500,
                    "expected_weekly_demand": 30,
                    "observed_weekly_demand": 18,
                    "confidence": 0.8,
                },
                {
                    "name": "Water",
                    "category": "beverages",
                    "price": None,
                    "expected_weekly_demand": 4,
                    "observed_weekly_demand": 7,
                    "confidence": 0.6,
                },
            ],
        }
    )

    assert report["summary"]["estimated_weekly_revenue"] == 9000.0
    assert report["summary"]["estimated_monthly_revenue"] == 36000.0
    assert report["summary"]["potential_revenue_gap_weekly"] == 6000.0
    assert report["demand_gaps"] == [
        {
            "name": "Bread",
            "expected_weekly_demand": 30.0,
            "observed_weekly_demand": 18.0,
            "gap_units": 12.0,
            "gap_revenue": 6000.0,
            "confidence": 0.8,
        }
    ]
    assert report["top_products"][0]["name"] == "Bread"


@pytest.mark.django_db
def test_service_builds_report_from_products_and_baselines():
    class StubBaselineService:
        def for_product(self, product):
            values = {
                "Coca-Cola 50cl PET": {"avg_weekly_turnover": 63.0},
                "Sliced White Bread": {"avg_weekly_turnover": 28.0},
            }
            return values.get(product.name)

    user = make_user("health-report")
    coke = make_product(user, name="Coca-Cola 50cl PET", category="beverages", selling_price=300, confidence_score=0.74)
    bread = make_product(user, name="Sliced White Bread", category="bakery", selling_price=800, confidence_score=0.62)
    make_burn_rate(coke, burn_rate_per_day=7.0, confidence_score=0.76)
    make_burn_rate(bread, burn_rate_per_day=2.0, confidence_score=0.61)

    make_baseline(
        product_name="Coca-Cola 50cl PET",
        category="beverages",
        generic_category="carbonated_soft_drink",
        avg_weekly_turnover=63.0,
        avg_unit_price=300.0,
    )
    make_baseline(
        product_name="Sliced White Bread",
        category="bakery",
        generic_category="bread",
        avg_weekly_turnover=28.0,
        avg_unit_price=800.0,
    )

    report = BusinessHealthReportService(baseline_service=StubBaselineService()).report_for_user(user)

    assert report["summary"]["estimated_weekly_revenue"] == 25900.0
    assert report["summary"]["estimated_monthly_revenue"] == 103600.0
    assert report["summary"]["potential_revenue_gap_weekly"] == 15400.0
    assert report["top_products"][0] == {
        "name": "Coca-Cola 50cl PET",
        "estimated_weekly_revenue": 14700.0,
    }
    assert report["demand_gaps"][0]["name"] == "Sliced White Bread"
    assert report["demand_gaps"][0]["gap_revenue"] == 11200.0
    assert report["demand_gaps"][1]["name"] == "Coca-Cola 50cl PET"
    assert "Closing the top 3 gaps could increase weekly revenue" in " ".join(report["insights"])
    assert "approximately ₦103,600.00 per month" in report["investor_summary"]
