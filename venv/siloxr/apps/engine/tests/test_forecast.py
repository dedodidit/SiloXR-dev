# backend/apps/engine/tests/test_forecast.py

from datetime import timedelta, date
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Product, InventoryEvent, BurnRate, ForecastSnapshot
from apps.inventory.events import EventProcessor
from apps.engine.forecast import (
    ForecastEngine,
    ForecastResult,
    ProjectionBuilder,
    StockoutDetector,
    ReorderAdvisor,
)


class TestProjectionBuilder(TestCase):

    def setUp(self):
        self.builder = ProjectionBuilder()

    def test_quantity_decreases_each_day(self):
        projections = self.builder.build(
            start_quantity=100.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=1.0,
            base_confidence=0.8,
            horizon_days=10,
        )
        quantities = [p.predicted_quantity for p in projections]
        # Each day should be <= previous day
        for i in range(1, len(quantities)):
            self.assertLessEqual(quantities[i], quantities[i - 1])

    def test_quantity_never_goes_negative(self):
        projections = self.builder.build(
            start_quantity=10.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=0.5,
            base_confidence=0.8,
            horizon_days=30,
        )
        for p in projections:
            self.assertGreaterEqual(p.predicted_quantity, 0.0)
            self.assertGreaterEqual(p.lower_bound, 0.0)
            self.assertGreaterEqual(p.upper_bound, 0.0)

    def test_lower_bound_always_lte_central(self):
        projections = self.builder.build(
            start_quantity=100.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=2.0,
            base_confidence=0.8,
            horizon_days=20,
        )
        for p in projections:
            self.assertLessEqual(p.lower_bound, p.predicted_quantity)

    def test_upper_bound_always_gte_central(self):
        projections = self.builder.build(
            start_quantity=100.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=2.0,
            base_confidence=0.8,
            horizon_days=20,
        )
        for p in projections:
            self.assertGreaterEqual(p.upper_bound, p.predicted_quantity)

    def test_confidence_decays_over_time(self):
        projections = self.builder.build(
            start_quantity=200.0,
            burn_rate_per_day=3.0,
            burn_rate_std_dev=1.5,
            base_confidence=0.9,
            horizon_days=30,
        )
        # Day 1 confidence should be higher than day 30
        self.assertGreater(
            projections[0].confidence_score,
            projections[-1].confidence_score,
        )

    def test_zero_std_dev_produces_identical_bounds(self):
        projections = self.builder.build(
            start_quantity=100.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=0.0,
            base_confidence=0.8,
            horizon_days=5,
        )
        for p in projections:
            self.assertEqual(p.lower_bound, p.predicted_quantity)
            self.assertEqual(p.upper_bound, p.predicted_quantity)


class TestStockoutDetector(TestCase):

    def setUp(self):
        self.detector = StockoutDetector()
        self.builder = ProjectionBuilder()

    def test_detects_central_stockout(self):
        projections = self.builder.build(
            start_quantity=20.0,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=0.5,
            base_confidence=0.8,
            horizon_days=30,
        )
        result = self.detector.detect(projections)
        self.assertIsNotNone(result["central"])
        self.assertLessEqual(result["central"], 5)

    def test_detects_pessimistic_before_central(self):
        projections = self.builder.build(
            start_quantity=30.0,
            burn_rate_per_day=3.0,
            burn_rate_std_dev=2.0,
            base_confidence=0.8,
            horizon_days=30,
        )
        result = self.detector.detect(projections)
        if result["pessimistic"] and result["central"]:
            self.assertLessEqual(result["pessimistic"], result["central"])

    def test_no_stockout_returns_none(self):
        projections = self.builder.build(
            start_quantity=10000.0,
            burn_rate_per_day=1.0,
            burn_rate_std_dev=0.1,
            base_confidence=0.9,
            horizon_days=30,
        )
        result = self.detector.detect(projections)
        self.assertIsNone(result["central"])
        self.assertIsNone(result["pessimistic"])

    def test_stockout_risk_high_when_imminent(self):
        risk = self.detector.compute_stockout_risk(
            days_until_stockout_pessimistic=2.0,
            days_until_stockout_central=4.0,
            confidence_score=0.85,
        )
        self.assertGreater(risk, 0.7)

    def test_stockout_risk_low_when_far_away(self):
        risk = self.detector.compute_stockout_risk(
            days_until_stockout_pessimistic=None,
            days_until_stockout_central=None,
            confidence_score=0.9,
        )
        self.assertLess(risk, 0.1)

    def test_low_confidence_caps_risk_below_1(self):
        risk = self.detector.compute_stockout_risk(
            days_until_stockout_pessimistic=1.0,
            days_until_stockout_central=2.0,
            confidence_score=0.1,
        )
        self.assertLess(risk, 1.0)


class TestForecastEngine(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="forecastuser", email="fc@siloxr.com", password="pass"
        )
        self.product = Product.objects.create(
            owner=self.user,
            name="Forecast Product",
            sku="FC-001",
            estimated_quantity=100.0,
            last_verified_quantity=100,
            reorder_point=20,
        )
        self.engine = ForecastEngine(horizon_days=30)

    def _make_burn_rate(self, rate=5.0, std_dev=1.0, confidence=0.8):
        return BurnRate.objects.create(
            product=self.product,
            burn_rate_per_day=rate,
            burn_rate_std_dev=std_dev,
            confidence_score=confidence,
            sample_days=20,
            sample_event_count=15,
            window_days=30,
        )

    def test_skips_gracefully_without_burn_rate(self):
        result = self.engine.run(self.product)
        self.assertTrue(result.skipped)
        self.assertIn("Learning Engine", result.skip_reason)

    def test_produces_snapshots_in_database(self):
        self._make_burn_rate()
        self.engine.run(self.product)
        snapshots = ForecastSnapshot.objects.filter(product=self.product)
        self.assertGreater(snapshots.count(), 0)

    def test_snapshots_have_valid_bounds(self):
        self._make_burn_rate()
        self.engine.run(self.product)
        for snap in ForecastSnapshot.objects.filter(product=self.product):
            self.assertLessEqual(snap.lower_bound, snap.predicted_quantity)
            self.assertGreaterEqual(snap.upper_bound, snap.predicted_quantity)
            self.assertGreaterEqual(snap.lower_bound, 0.0)

    def test_stockout_detected_correctly(self):
        # 100 units at 10/day = stockout around day 10
        self._make_burn_rate(rate=10.0, std_dev=1.0)
        result = self.engine.run(self.product)
        self.assertIsNotNone(result.days_until_stockout)
        self.assertAlmostEqual(result.days_until_stockout, 10.0, delta=2.0)

    def test_reorder_point_crossed_before_stockout(self):
        # reorder_point=20, stock=100, burn=10/day → crosses ~day 8
        self._make_burn_rate(rate=10.0, std_dev=0.5)
        result = self.engine.run(self.product)
        if result.days_until_reorder_point and result.days_until_stockout:
            self.assertLess(
                result.days_until_reorder_point,
                result.days_until_stockout,
            )

    def test_upsert_does_not_duplicate_snapshots(self):
        self._make_burn_rate()
        self.engine.run(self.product)
        count_first = ForecastSnapshot.objects.filter(product=self.product).count()
        # Run again — same dates, should upsert not append
        self._make_burn_rate(rate=4.8)
        self.engine.run(self.product)
        count_second = ForecastSnapshot.objects.filter(product=self.product).count()
        self.assertEqual(count_first, count_second)

    def test_forecast_summary_is_human_readable(self):
        self._make_burn_rate(rate=10.0)
        result = self.engine.run(self.product)
        summary = result.forecast_summary
        self.assertIn("days", summary)
        self.assertIn("Confidence", summary)

    def test_zero_burn_rate_produces_stable_forecast(self):
        BurnRate.objects.create(
            product=self.product,
            burn_rate_per_day=0.0,
            burn_rate_std_dev=0.0,
            confidence_score=0.15,
            sample_days=0,
            sample_event_count=0,
            window_days=30,
        )
        result = self.engine.run(self.product)
        self.assertFalse(result.skipped)
        self.assertIsNone(result.days_until_stockout)
        for proj in result.projections:
            self.assertEqual(proj.predicted_quantity, self.product.estimated_quantity)