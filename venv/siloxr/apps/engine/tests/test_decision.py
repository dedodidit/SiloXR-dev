# backend/apps/engine/tests/test_decision.py

from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import DecisionLog, Product
from apps.engine.decision import (
    ActionSelector,
    DecisionContext,
    DecisionEngine,
    DecisionOutput,
    ReasoningComposer,
    LOW_CONFIDENCE_FLOOR,
    THRESHOLD_MATRIX,
)
from apps.engine.forecast import ForecastResult


def _make_context(
    product,
    stockout_risk=0.0,
    days_central=None,
    days_pess=None,
    days_reorder=None,
    confidence=0.8,
    qty=100.0,
    reorder_point=20.0,
    forecast=None,
):
    if forecast is None:
        forecast = ForecastResult(
            product_id=str(product.id),
            product_sku=product.sku,
            horizon_days=30,
            days_until_stockout=days_central,
            days_until_stockout_pessimistic=days_pess,
            days_until_reorder_point=days_reorder,
            stockout_risk_score=stockout_risk,
            confidence_score=confidence,
            initial_quantity=qty,
            burn_rate_used=5.0,
        )
    return DecisionContext(
        product=product,
        forecast=forecast,
        stockout_risk=stockout_risk,
        days_until_stockout=days_central,
        days_until_stockout_pessimistic=days_pess,
        days_until_reorder_point=days_reorder,
        confidence_score=confidence,
        estimated_quantity=qty,
        reorder_point=reorder_point,
        latest_snapshot=None,
    )


class TestActionSelector(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="decisionuser", email="d@siloxr.com",
            password="pass", tier="pro",
        )
        self.product = Product.objects.create(
            owner=self.user, name="Widget", sku="WGT-001",
            estimated_quantity=50.0, last_verified_quantity=50,
        )
        self.selector = ActionSelector()

    def test_critical_alert_when_risk_very_high_and_days_imminent(self):
        ctx = _make_context(
            self.product,
            stockout_risk=0.90,
            days_pess=2.0,
            confidence=0.75,
        )
        action, conf = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.ALERT_CRITICAL)
        self.assertGreater(conf, 0.0)

    def test_low_confidence_forces_check_stock(self):
        ctx = _make_context(
            self.product,
            stockout_risk=0.85,
            days_pess=1.0,
            confidence=LOW_CONFIDENCE_FLOOR - 0.01,
        )
        action, _ = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.CHECK_STOCK)

    def test_hold_when_no_risk(self):
        ctx = _make_context(
            self.product,
            stockout_risk=0.01,
            confidence=0.9,
        )
        action, _ = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.HOLD)

    def test_reorder_fires_at_correct_threshold(self):
        ctx = _make_context(
            self.product,
            stockout_risk=0.40,
            days_pess=12.0,
            confidence=0.6,
        )
        action, _ = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.REORDER)

    def test_alert_low_fires_before_critical(self):
        ctx = _make_context(
            self.product,
            stockout_risk=0.60,
            days_pess=6.0,
            confidence=0.65,
        )
        action, _ = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.ALERT_LOW)

    def test_cooldown_suppresses_repeat_action(self):
        # Create a recent unacknowledged ALERT_CRITICAL
        DecisionLog.objects.create(
            product=self.product,
            action=DecisionLog.ALERT_CRITICAL,
            reasoning="Test",
            confidence_score=0.8,
            estimated_quantity_at_decision=50.0,
            expires_at=timezone.now() + timedelta(hours=6),
            is_acknowledged=False,
        )
        ctx = _make_context(
            self.product,
            stockout_risk=0.92,
            days_pess=1.0,
            confidence=0.75,
        )
        action, _ = self.selector.select(ctx)
        # Should fall through to ALERT_LOW or lower — CRITICAL is on cooldown
        self.assertNotEqual(action, DecisionLog.ALERT_CRITICAL)

    def test_acknowledged_decision_does_not_trigger_cooldown(self):
        # Acknowledged decisions do not block new ones
        DecisionLog.objects.create(
            product=self.product,
            action=DecisionLog.ALERT_CRITICAL,
            reasoning="Test",
            confidence_score=0.8,
            estimated_quantity_at_decision=50.0,
            expires_at=timezone.now() + timedelta(hours=6),
            is_acknowledged=True,   # acknowledged — should not count for cooldown
        )
        ctx = _make_context(
            self.product,
            stockout_risk=0.92,
            days_pess=1.0,
            confidence=0.75,
        )
        action, _ = self.selector.select(ctx)
        self.assertEqual(action, DecisionLog.ALERT_CRITICAL)


class TestReasoningComposer(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="reasonuser", email="r@siloxr.com", password="pass"
        )
        self.product = Product.objects.create(
            owner=self.user, name="Gadget", sku="GDG-001",
            estimated_quantity=80.0, last_verified_quantity=80,
        )
        self.composer = ReasoningComposer()

    def _ctx(self, **kwargs):
        return _make_context(self.product, **kwargs)

    def test_all_actions_produce_non_empty_reasoning(self):
        actions = [
            DecisionLog.ALERT_CRITICAL,
            DecisionLog.ALERT_LOW,
            DecisionLog.REORDER,
            DecisionLog.CHECK_STOCK,
            DecisionLog.MONITOR,
            DecisionLog.HOLD,
        ]
        for action in actions:
            ctx = self._ctx(
                stockout_risk=0.9, days_pess=2.0,
                days_central=5.0, confidence=0.75
            )
            text = self.composer.compose(action, ctx, 0.75)
            self.assertGreater(len(text), 20, f"Empty reasoning for {action}")

    def test_reasoning_never_sounds_absolute(self):
        """Reasoning must use hedged language — never absolute commands."""
        absolute_words = ["will definitely", "must ", "you must", "guaranteed"]
        for action in [DecisionLog.ALERT_CRITICAL, DecisionLog.REORDER]:
            ctx = self._ctx(
                stockout_risk=0.9, days_pess=2.0, confidence=0.8
            )
            text = self.composer.compose(action, ctx, 0.8).lower()
            for word in absolute_words:
                self.assertNotIn(word, text, f"Found absolute language '{word}' in {action} reasoning")

    def test_reasoning_includes_confidence_percentage(self):
        ctx = self._ctx(stockout_risk=0.6, days_pess=5.0, confidence=0.72)
        text = self.composer.compose(DecisionLog.ALERT_LOW, ctx, 0.72)
        self.assertIn("72%", text)

    def test_reasoning_includes_sku(self):
        ctx = self._ctx(confidence=0.8)
        for action in [DecisionLog.HOLD, DecisionLog.MONITOR]:
            text = self.composer.compose(action, ctx, 0.8)
            self.assertIn("GDG-001", text)

    def test_check_stock_mentions_low_confidence_when_appropriate(self):
        ctx = self._ctx(confidence=0.15)
        text = self.composer.compose(DecisionLog.CHECK_STOCK, ctx, 0.15)
        self.assertIn("confidence", text.lower())


class TestDecisionEngine(TestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username="enguser", email="eng@siloxr.com",
            password="pass", tier="pro",
        )
        self.product = Product.objects.create(
            owner=self.user, name="Engine Widget", sku="ENG-001",
            estimated_quantity=100.0, last_verified_quantity=100,
            reorder_point=20,
        )
        self.engine = DecisionEngine()

    def _forecast(self, **kwargs):
        defaults = dict(
            product_id=str(self.product.id),
            product_sku=self.product.sku,
            horizon_days=30,
            days_until_stockout=None,
            days_until_stockout_pessimistic=None,
            stockout_risk_score=0.02,
            confidence_score=0.82,
            initial_quantity=100.0,
            burn_rate_used=5.0,
        )
        defaults.update(kwargs)
        return ForecastResult(**defaults)

    def test_run_persists_decision_log(self):
        forecast = self._forecast()
        output = self.engine.run(self.product, forecast)
        self.assertIsNotNone(output.decision_log_id)
        log = DecisionLog.objects.get(id=output.decision_log_id)
        self.assertEqual(log.product, self.product)

    def test_decision_log_has_all_required_fields(self):
        forecast = self._forecast(stockout_risk_score=0.6, days_until_stockout_pessimistic=5.0)
        output = self.engine.run(self.product, forecast)
        log = DecisionLog.objects.get(id=output.decision_log_id)
        self.assertTrue(log.reasoning)
        self.assertGreater(log.confidence_score, 0)
        self.assertIsNotNone(log.expires_at)
        self.assertIn(log.action, dict(DecisionLog.ACTION_CHOICES))

    def test_skipped_forecast_produces_check_stock(self):
        forecast = ForecastResult(
            product_id=str(self.product.id),
            product_sku=self.product.sku,
            horizon_days=30,
            skipped=True,
            skip_reason="No burn rate available.",
        )
        output = self.engine.run(self.product, forecast)
        self.assertTrue(output.skipped)
        self.assertEqual(output.action, DecisionLog.CHECK_STOCK)

    def test_decision_output_severity_matches_action(self):
        forecast = self._forecast(
            stockout_risk_score=0.90,
            days_until_stockout_pessimistic=2.0,
            confidence_score=0.75,
        )
        output = self.engine.run(self.product, forecast)
        expected_severity = DecisionLog.ACTION_SEVERITY.get(output.action)
        self.assertEqual(output.severity, expected_severity)

    def test_expires_at_set_correctly_per_action(self):
        from apps.engine.decision import ACTION_TTL_HOURS
        forecast = self._forecast()
        output = self.engine.run(self.product, forecast)
        log = DecisionLog.objects.get(id=output.decision_log_id)
        expected_ttl = timedelta(hours=ACTION_TTL_HOURS[log.action])
        actual_ttl = log.expires_at - log.created_at
        self.assertAlmostEqual(
            actual_ttl.total_seconds(),
            expected_ttl.total_seconds(),
            delta=5,
        )

    def test_full_engine_chain_integration(self):
        """
        End-to-end: InventoryEvent → Learning → Forecast → Decision.
        Verifies the full signal chain produces a DecisionLog for a Pro user.
        """
        from apps.inventory.events import EventProcessor
        from apps.inventory.models import InventoryEvent

        processor = EventProcessor(self.product)
        # Record enough sales to train the learning engine
        for i in range(12):
            processor.record(
                event_type=InventoryEvent.SALE,
                quantity=5,
                occurred_at=timezone.now() - timedelta(days=i),
                recorded_by=self.user,
            )

        # Decision log should have been auto-generated via signal chain
        logs = DecisionLog.objects.filter(product=self.product)
        self.assertGreater(logs.count(), 0)

        latest = logs.order_by("-created_at").first()
        self.assertIn(latest.action, dict(DecisionLog.ACTION_CHOICES))
        self.assertGreater(len(latest.reasoning), 20)
        self.assertGreater(latest.confidence_score, 0)