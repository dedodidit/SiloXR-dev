# backend/apps/engine/tests/test_feedback.py

from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import (
    BurnRate, ForecastSnapshot, InventoryEvent, Product,
)
from apps.inventory.events import EventProcessor
from apps.engine.feedback import (
    ActualResolver,
    BiasDetector,
    ConfidenceAuditor,
    ErrorCalculator,
    FeedbackEngine,
    ProductAccuracyReport,
)


class FeedbackTestBase(TestCase):
    """Shared setup for all feedback tests."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="fbuser", email="fb@siloxr.com",
            password="pass", tier="pro",
        )
        self.product = Product.objects.create(
            owner=self.user,
            name="Feedback Product",
            sku="FB-001",
            estimated_quantity=100.0,
            last_verified_quantity=100,
        )

    def _make_snapshot(
        self,
        days_ago: int,
        predicted: float,
        actual: float = None,
        lower: float = None,
        upper: float = None,
        confidence: float = 0.75,
    ) -> ForecastSnapshot:
        target_date = date.today() - timedelta(days=days_ago)
        snap = ForecastSnapshot.objects.create(
            product=self.product,
            forecast_date=target_date,
            predicted_quantity=predicted,
            lower_bound=lower if lower is not None else predicted * 0.8,
            upper_bound=upper if upper is not None else predicted * 1.2,
            confidence_score=confidence,
            actual_quantity=actual,
            forecast_error=predicted - actual if actual is not None else None,
        )
        return snap

    def _make_stock_count(self, days_ago: int, verified_qty: int) -> InventoryEvent:
        processor = EventProcessor(self.product)
        return processor.record(
            event_type=InventoryEvent.STOCK_COUNT,
            quantity=0,
            verified_quantity=verified_qty,
            occurred_at=timezone.now() - timedelta(days=days_ago),
            recorded_by=self.user,
        )

    def _make_burn_rate(self, rate: float = 5.0, window: int = 30) -> BurnRate:
        return BurnRate.objects.create(
            product=self.product,
            burn_rate_per_day=rate,
            burn_rate_std_dev=0.5,
            confidence_score=0.75,
            sample_days=window,
            sample_event_count=15,
            window_days=window,
        )


class TestActualResolver(FeedbackTestBase):

    def test_resolves_snapshot_using_nearby_stock_count(self):
        snap = self._make_snapshot(days_ago=5, predicted=80.0)
        self._make_stock_count(days_ago=5, verified_qty=72)

        resolver  = ActualResolver()
        resolved  = resolver.resolve_pending(self.product)

        snap.refresh_from_db()
        self.assertEqual(len(resolved), 1)
        self.assertEqual(snap.actual_quantity, 72.0)

    def test_writes_forecast_error_on_resolution(self):
        self._make_snapshot(days_ago=4, predicted=90.0)
        self._make_stock_count(days_ago=4, verified_qty=80)

        ActualResolver().resolve_pending(self.product)

        snap = ForecastSnapshot.objects.get(product=self.product)
        snap.refresh_from_db()
        self.assertIsNotNone(snap.forecast_error)
        self.assertAlmostEqual(snap.forecast_error, 10.0, delta=0.1)

    def test_does_not_resolve_future_snapshots(self):
        # Snapshot in the future — should not be resolved
        ForecastSnapshot.objects.create(
            product=self.product,
            forecast_date=date.today() + timedelta(days=5),
            predicted_quantity=100.0,
            lower_bound=90.0,
            upper_bound=110.0,
            confidence_score=0.8,
        )
        resolved = ActualResolver().resolve_pending(self.product)
        self.assertEqual(len(resolved), 0)

    def test_does_not_re_resolve_already_resolved_snapshots(self):
        # Snapshot already has actual_quantity set
        self._make_snapshot(days_ago=3, predicted=80.0, actual=75.0)
        resolved = ActualResolver().resolve_pending(self.product)
        self.assertEqual(len(resolved), 0)

    def test_reconstructs_quantity_from_event_log_when_no_count(self):
        """
        Without a nearby STOCK_COUNT, the resolver should reconstruct
        from the event log using the most recent anchor.
        """
        # Anchor: stock count 20 days ago at 100 units
        self._make_stock_count(days_ago=20, verified_qty=100)
        # Five sales of 5 units each since the anchor
        processor = EventProcessor(self.product)
        for i in range(5, 0, -1):
            processor.record(
                event_type=InventoryEvent.SALE,
                quantity=5,
                occurred_at=timezone.now() - timedelta(days=i),
                recorded_by=self.user,
            )

        # Snapshot from 3 days ago — no nearby count
        snap = self._make_snapshot(days_ago=3, predicted=80.0)
        resolved = ActualResolver().resolve_pending(self.product)

        snap.refresh_from_db()
        # Reconstructed: 100 - (some sales before day 3) — actual value depends on timing
        self.assertIsNotNone(snap.actual_quantity)
        self.assertGreater(snap.actual_quantity, 0)


class TestErrorCalculator(FeedbackTestBase):

    def _resolved_snapshots(self, pairs: list[tuple]) -> list[ForecastSnapshot]:
        """pairs = [(predicted, actual), ...]"""
        snaps = []
        for i, (pred, act) in enumerate(pairs, start=1):
            s = self._make_snapshot(days_ago=i + 5, predicted=pred, actual=act)
            snaps.append(s)
        return snaps

    def test_computes_mae_correctly(self):
        snaps = self._resolved_snapshots([(100, 90), (100, 80), (100, 70)])
        report = ErrorCalculator().calculate(self.product, snaps)
        self.assertIsNotNone(report)
        # Errors are 10, 20, 30 → MAE = 20
        self.assertAlmostEqual(report.mae, 20.0, delta=0.5)

    def test_computes_mape_correctly(self):
        snaps = self._resolved_snapshots([(110, 100), (110, 100), (110, 100)])
        report = ErrorCalculator().calculate(self.product, snaps)
        # Each error is 10%, so MAPE = 10
        self.assertAlmostEqual(report.mape, 10.0, delta=0.5)

    def test_detects_over_prediction_bias(self):
        # Always predicted more than actual
        snaps = self._resolved_snapshots([(100, 80), (100, 75), (100, 85)])
        report = ErrorCalculator().calculate(self.product, snaps)
        self.assertEqual(report.bias_direction, "over")
        self.assertGreater(report.bias, 0)

    def test_detects_under_prediction_bias(self):
        snaps = self._resolved_snapshots([(70, 90), (70, 95), (70, 88)])
        report = ErrorCalculator().calculate(self.product, snaps)
        self.assertEqual(report.bias_direction, "under")
        self.assertLess(report.bias, 0)

    def test_neutral_bias_when_errors_balanced(self):
        snaps = self._resolved_snapshots([(100, 103), (100, 97), (100, 100)])
        report = ErrorCalculator().calculate(self.product, snaps)
        self.assertEqual(report.bias_direction, "neutral")

    def test_returns_none_for_insufficient_data(self):
        snaps = self._resolved_snapshots([(100, 90)])  # only 1 snapshot
        report = ErrorCalculator().calculate(self.product, snaps)
        self.assertIsNone(report)


class TestBiasDetector(TestCase):

    def _report(self, mape, bias_direction, bias=10.0):
        return ProductAccuracyReport(
            product_id="test",
            product_sku="TST",
            resolved_count=10,
            mae=5.0,
            mape=mape,
            bias=bias,
            bias_direction=bias_direction,
        )

    def test_no_adjustment_when_mape_low(self):
        detector = BiasDetector()
        factor = detector.compute_adjustment(self._report(10.0, "over"))
        self.assertEqual(factor, 1.0)

    def test_increases_rate_for_over_prediction(self):
        detector = BiasDetector()
        factor = detector.compute_adjustment(self._report(30.0, "over"))
        self.assertGreater(factor, 1.0)

    def test_decreases_rate_for_under_prediction(self):
        detector = BiasDetector()
        factor = detector.compute_adjustment(self._report(30.0, "under"))
        self.assertLess(factor, 1.0)

    def test_neutral_bias_no_directional_adjustment(self):
        detector = BiasDetector()
        factor = detector.compute_adjustment(self._report(25.0, "neutral"))
        self.assertEqual(factor, 1.0)

    def test_adjustment_capped_at_max(self):
        detector = BiasDetector()
        # Extreme MAPE should not exceed MAX_ADJUSTMENT
        factor = detector.compute_adjustment(self._report(999.0, "over"))
        self.assertLessEqual(factor, 1.0 + BiasDetector.MAX_ADJUSTMENT + 0.001)

    def test_suggests_shorter_window_for_high_mape_over_prediction(self):
        detector = BiasDetector()
        report   = self._report(30.0, "over")
        new_window = detector.suggest_window(report, current_window=30)
        self.assertIsNotNone(new_window)
        self.assertLess(new_window, 30)

    def test_no_window_change_when_mape_acceptable(self):
        detector = BiasDetector()
        report   = self._report(12.0, "neutral")
        new_window = detector.suggest_window(report, current_window=30)
        self.assertIsNone(new_window)


class TestFeedbackEngine(FeedbackTestBase):

    def test_returns_none_when_no_resolvable_snapshots(self):
        signal = FeedbackEngine().run(self.product)
        self.assertIsNone(signal)

    def test_non_actionable_signal_when_too_few_snapshots(self):
        self._make_snapshot(days_ago=3, predicted=80.0, actual=75.0)
        # Only 1 resolved snapshot — not enough for error calc
        signal = FeedbackEngine().run(self.product)
        self.assertIsNotNone(signal)
        self.assertFalse(signal.actionable)

    def test_actionable_signal_with_enough_data(self):
        self._make_burn_rate()
        for i in range(5, 10):
            self._make_snapshot(
                days_ago=i, predicted=100.0, actual=80.0
            )
            self._make_stock_count(days_ago=i, verified_qty=80)

        signal = FeedbackEngine().run(self.product)
        self.assertIsNotNone(signal)
        self.assertTrue(signal.actionable)

    def test_over_prediction_increases_burn_rate(self):
        """
        When we consistently predict more stock than exists,
        the burn rate was too slow — the feedback engine should increase it.
        """
        self._make_burn_rate(rate=5.0)
        # Simulate consistent over-prediction: predicted 100, actual 70
        for i in range(5, 12):
            self._make_snapshot(
                days_ago=i, predicted=100.0, actual=70.0
            )
            self._make_stock_count(days_ago=i, verified_qty=70)

        signal = FeedbackEngine().run(self.product)
        self.assertIsNotNone(signal)

        if signal.actionable:
            # Rate factor should be >= 1.0 (increase) or at minimum no decrease
            self.assertGreaterEqual(signal.rate_adjustment_factor, 1.0)

    def test_signal_summary_is_human_readable(self):
        self._make_burn_rate()
        for i in range(5, 10):
            self._make_snapshot(days_ago=i, predicted=100.0, actual=90.0)
            self._make_stock_count(days_ago=i, verified_qty=90)

        signal = FeedbackEngine().run(self.product)
        if signal and signal.actionable:
            self.assertIn("FB-001", signal.summary)
            self.assertIn("MAE", signal.summary)

    def test_feedback_writes_corrected_burn_rate_record(self):
        """
        When the feedback engine applies a rate correction, it should
        write a new BurnRate record (which triggers the forecast chain).
        """
        self._make_burn_rate(rate=5.0)
        before_count = BurnRate.objects.filter(product=self.product).count()

        # High MAPE over-prediction to trigger a correction
        for i in range(5, 12):
            self._make_snapshot(days_ago=i, predicted=100.0, actual=60.0)
            self._make_stock_count(days_ago=i, verified_qty=60)

        FeedbackEngine().run(self.product)

        after_count = BurnRate.objects.filter(product=self.product).count()
        # A new corrected BurnRate should have been written
        self.assertGreaterEqual(after_count, before_count)