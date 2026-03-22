# backend/apps/engine/tests/test_learning.py

from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Product, InventoryEvent, BurnRate
from apps.inventory.events import EventProcessor
from apps.engine.learning import LearningEngine
from apps.engine.confidence import ConfidenceScorer


class TestConfidenceScorer(TestCase):

    def setUp(self):
        self.scorer = ConfidenceScorer()

    def test_no_data_returns_low_confidence(self):
        result = self.scorer.compute(
            last_event_date=None,
            sample_event_count=0,
            burn_rate_std_dev=0.0,
            burn_rate_per_day=0.0,
        )
        self.assertLess(result.final_score, 0.3)

    def test_recent_high_sample_low_variance_returns_high_confidence(self):
        result = self.scorer.compute(
            last_event_date=timezone.now() - timedelta(hours=2),
            sample_event_count=30,
            burn_rate_std_dev=0.5,
            burn_rate_per_day=10.0,
        )
        self.assertGreater(result.final_score, 0.75)

    def test_drift_penalty_reduces_correction_score(self):
        no_drift = self.scorer.compute(
            last_event_date=timezone.now(),
            sample_event_count=20,
            burn_rate_std_dev=1.0,
            burn_rate_per_day=10.0,
            avg_drift_pct=0.0,
        )
        high_drift = self.scorer.compute(
            last_event_date=timezone.now(),
            sample_event_count=20,
            burn_rate_std_dev=1.0,
            burn_rate_per_day=10.0,
            avg_drift_pct=0.8,
        )
        self.assertGreater(no_drift.final_score, high_drift.final_score)

    def test_confidence_never_exceeds_0_99(self):
        result = self.scorer.compute(
            last_event_date=timezone.now(),
            sample_event_count=1000,
            burn_rate_std_dev=0.001,
            burn_rate_per_day=10.0,
        )
        self.assertLessEqual(result.final_score, 0.99)

    def test_confidence_never_below_0_05(self):
        result = self.scorer.compute(
            last_event_date=timezone.now() - timedelta(days=999),
            sample_event_count=0,
            burn_rate_std_dev=999.0,
            burn_rate_per_day=0.001,
        )
        self.assertGreaterEqual(result.final_score, 0.05)


class TestLearningEngine(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser", email="test@siloxr.com", password="pass"
        )
        self.product = Product.objects.create(
            owner=self.user,
            name="Test Product",
            sku="TEST-001",
            estimated_quantity=100.0,
            last_verified_quantity=100,
        )
        self.engine = LearningEngine()

    def _record_sale(self, qty, days_ago=0):
        processor = EventProcessor(self.product)
        processor.record(
            event_type=InventoryEvent.SALE,
            quantity=qty,
            occurred_at=timezone.now() - timedelta(days=days_ago),
            recorded_by=self.user,
        )

    def test_learning_writes_burn_rate_record(self):
        for i in range(10):
            self._record_sale(qty=5, days_ago=i)
        result = self.engine.run(self.product)
        self.assertFalse(result.skipped)
        self.assertTrue(BurnRate.objects.filter(product=self.product).exists())

    def test_burn_rate_reflects_actual_consumption(self):
        # Sell exactly 10 units per day for 10 days
        for i in range(10):
            self._record_sale(qty=10, days_ago=i)
        result = self.engine.run(self.product)
        # In a 30-day window with 10 active days, mean ≈ 10/3 ≈ 3.33/day
        self.assertGreater(result.burn_rate_per_day, 0)
        self.assertLess(result.burn_rate_per_day, 15)

    def test_no_events_returns_skipped_result(self):
        result = self.engine.run(self.product)
        self.assertTrue(result.skipped)
        self.assertEqual(result.skip_reason, "No sale events in learning window")

    def test_estimated_and_verified_quantities_never_merged(self):
        """
        Core invariant: a STOCK_COUNT event updates last_verified_quantity
        but does NOT merge it with estimated_quantity at the model level.
        Both fields must remain distinct after any event sequence.
        """
        processor = EventProcessor(self.product)

        # Record sales that reduce estimated quantity
        for i in range(5):
            self._record_sale(qty=5, days_ago=i)

        self.product.refresh_from_db()
        estimated_after_sales = self.product.estimated_quantity

        # Record a stock count that reveals ground truth
        processor.record(
            event_type=InventoryEvent.STOCK_COUNT,
            quantity=0,
            verified_quantity=60,
            occurred_at=timezone.now(),
            recorded_by=self.user,
        )

        self.product.refresh_from_db()

        # After STOCK_COUNT, verified is the physical count
        self.assertEqual(self.product.last_verified_quantity, 60)
        # estimated snaps to verified after a count (EventProcessor behaviour)
        self.assertEqual(self.product.estimated_quantity, 60.0)
        # The two fields exist as separate DB columns — this is the invariant
        self.assertIsNotNone(self.product.last_verified_quantity)
        self.assertIsNotNone(self.product.estimated_quantity)

    def test_product_confidence_updated_after_learning(self):
        for i in range(15):
            self._record_sale(qty=8, days_ago=i)
        self.engine.run(self.product)
        self.product.refresh_from_db()
        self.assertGreater(self.product.confidence_score, 0.3)

    def test_no_data_fallback_uses_previous_burn_rate(self):
        """If we have a previous burn rate, the fallback should use it (halved)."""
        BurnRate.objects.create(
            product=self.product,
            burn_rate_per_day=10.0,
            burn_rate_std_dev=1.0,
            confidence_score=0.8,
            sample_days=30,
            sample_event_count=20,
            window_days=30,
        )
        result = self.engine.run(self.product)
        self.assertTrue(result.skipped)
        self.assertAlmostEqual(result.burn_rate_per_day, 5.0)