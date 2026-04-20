from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.inventory.models import InventoryEvent, Product
from apps.notifications.models import Notification, NotificationThrottle
from apps.notifications.reminders import (
    maybe_send_automated_product_update_reminder,
    send_product_update_reminders,
)
from apps.notifications.dispatch import dispatch_dashboard_insights, _send_email_message, notification_channel_status
from apps.notifications.business_briefs import resolve_business_brief_type, send_business_briefs
from apps.notifications.router import NotificationRouter
from apps.notifications.services.inactivity_engine import evaluate_user_inactivity
from apps.notifications.services.insight_engine import generate_product_insight
from apps.notifications.services.notification_service import NotificationDispatchResult, send_notification
from apps.notifications.management.commands.run_proactive_checks import run_proactive_checks


class ProductUpdateReminderTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        cache.clear()

    def _make_user(self, **overrides):
        defaults = {
            "username": f"user_{self.user_model.objects.count() + 1}",
            "email": f"user_{self.user_model.objects.count() + 1}@example.com",
            "preferred_channel": "email",
            "email_notifications_enabled": True,
            "tier": self.user_model.TIER_FREE,
        }
        defaults.update(overrides)
        return self.user_model.objects.create_user(password="Secret123!", **defaults)

    def _make_product(self, user, **overrides):
        defaults = {
            "owner": user,
            "name": f"Product {Product.objects.count() + 1}",
            "sku": f"SKU-{Product.objects.count() + 1}",
            "unit": "packs",
            "estimated_quantity": 12,
            "last_verified_quantity": 12,
            "last_verified_at": timezone.now() - timedelta(days=20),
            "confidence_score": 0.45,
        }
        defaults.update(overrides)
        return Product.objects.create(**defaults)

    @patch("apps.notifications.dispatch.send_mail")
    def test_route_product_update_reminder_prefers_email(self, send_mail_mock):
        send_mail_mock.return_value = 1
        user = self._make_user()
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.email)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_IN_APP).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_EMAIL).count(), 1)
        self.assertTrue(
            NotificationThrottle.objects.filter(user=user, channel="upd_reminder").exists()
        )
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.dispatch.send_mail")
    def test_route_product_update_reminder_sends_email_when_ready(self, send_mail_mock):
        send_mail_mock.return_value = 1
        user = self._make_user(preferred_channel="email")
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.email)
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.dispatch.send_mail")
    def test_send_product_update_reminders_respects_cadence(self, send_mail_mock):
        send_mail_mock.return_value = 1
        user = self._make_user()
        self._make_product(user, sku="SKU-ST-1")

        first = send_product_update_reminders(cadence_hours=24)
        second = send_product_update_reminders(cadence_hours=24)

        self.assertEqual(first.users_notified, 1)
        self.assertEqual(second.users_notified, 0)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_IN_APP).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_EMAIL).count(), 1)
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.dispatch.send_mail")
    def test_maybe_send_automated_product_update_reminder_debounces_checks(self, send_mail_mock):
        send_mail_mock.return_value = 1
        user = self._make_user()
        self._make_product(user, sku="SKU-AUTO-1")

        first = maybe_send_automated_product_update_reminder(
            user,
            cadence_hours=24,
            check_interval_minutes=60,
        )
        second = maybe_send_automated_product_update_reminder(
            user,
            cadence_hours=24,
            check_interval_minutes=60,
        )

        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_IN_APP).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_EMAIL).count(), 1)
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.dispatch.send_mail")
    def test_dispatch_dashboard_insights_routes_once_per_fingerprint(self, send_mail_mock):
        send_mail_mock.return_value = 1
        user = self._make_user()

        contextual = [
            {
                "title": "Trend shift",
                "summary": "Demand is climbing faster than last week.",
                "recommendation": "Review your top movers today.",
                "confidence": 0.68,
            }
        ]
        managerial = [
            {
                "title": "Revenue at risk",
                "summary": "Two critical products are exposing near-term sales.",
                "recommendation": "Open the dashboard and clear the critical queue first.",
                "value": "N25,000",
                "tone": "critical",
                "target": "decisions",
            }
        ]

        first = dispatch_dashboard_insights(user, contextual, managerial, cadence_hours=12)
        second = dispatch_dashboard_insights(user, contextual, managerial, cadence_hours=12)

        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_IN_APP).count(), 2)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_EMAIL).count(), 2)
        self.assertEqual(send_mail_mock.call_count, 2)

        html_message = send_mail_mock.call_args.kwargs.get("html_message", "")
        self.assertIn("/dashboard#decisions", html_message)

    @override_settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="hello@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="SiloXR <hello@example.com>",
    )
    @patch("apps.notifications.dispatch.send_mail", return_value=1)
    def test_send_email_message_returns_false_when_send_fails(self, send_mail_mock):
        user = self._make_user()
        send_mail_mock.return_value = 0

        delivered = _send_email_message(user, "Test", "Body")

        self.assertFalse(delivered)

    @override_settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="hello@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="SiloXR <hello@example.com>",
    )
    def test_notification_channel_status_flags_ready_email(self):
        user = self._make_user()

        status = notification_channel_status(user)

        self.assertTrue(status["email"]["ready"])
        self.assertEqual(status["recommended_channel"], "email")

    def test_resolve_business_brief_type_uses_business_windows(self):
        opening = datetime(2026, 3, 23, 7, 30, tzinfo=dt_timezone.utc)
        closing = datetime(2026, 3, 23, 17, 30, tzinfo=dt_timezone.utc)
        midday = datetime(2026, 3, 23, 12, 0, tzinfo=dt_timezone.utc)

        self.assertEqual(resolve_business_brief_type(opening), "opening")
        self.assertEqual(resolve_business_brief_type(closing), "closing")
        self.assertIsNone(resolve_business_brief_type(midday))

    @patch("apps.notifications.business_briefs.dispatch_dashboard_brief", return_value=True)
    @patch("apps.api.views.DashboardViewSet._build_summary_data")
    def test_send_business_briefs_records_once_per_window(self, build_summary_mock, dispatch_brief_mock):
        user = self._make_user()
        build_summary_mock.return_value = {
            "managerial_brief": {"headline": "Stable", "subtext": "Keep counts current."},
            "contextual_insights": [],
            "managerial_signals": [],
        }

        first = send_business_briefs(brief_type="opening", user_limit=1)
        second = send_business_briefs(brief_type="opening", user_limit=1)

        self.assertEqual(first.briefs_sent, 1)
        self.assertEqual(second.briefs_sent, 0)
        dispatch_brief_mock.assert_called_once()


class InsightNotificationSystemTests(TransactionTestCase):
    def setUp(self):
        self.user_model = get_user_model()
        cache.clear()

    def _make_user(self, **overrides):
        defaults = {
            "username": f"insight_user_{self.user_model.objects.count() + 1}",
            "email": f"insight_{self.user_model.objects.count() + 1}@example.com",
            "preferred_channel": "email",
            "email_notifications_enabled": True,
            "tier": self.user_model.TIER_FREE,
        }
        defaults.update(overrides)
        return self.user_model.objects.create_user(password="Secret123!", **defaults)

    def _make_product(self, user, **overrides):
        defaults = {
            "owner": user,
            "name": f"Product {Product.objects.count() + 1}",
            "sku": f"INS-{Product.objects.count() + 1}",
            "unit": "packs",
            "estimated_quantity": 10,
            "last_verified_quantity": 10,
            "last_verified_at": timezone.now() - timedelta(days=12),
            "confidence_score": 0.7,
            "selling_price": 1000,
            "cost_price": 600,
        }
        defaults.update(overrides)
        return Product.objects.create(**defaults)

    def _add_sales(self, product, quantities, base_days_ago: int = 1):
        now = timezone.now()
        for offset, quantity in enumerate(quantities):
            InventoryEvent.objects.create(
                product=product,
                recorded_by=product.owner,
                event_type=InventoryEvent.SALE,
                quantity=quantity,
                notes="sale",
                occurred_at=now - timedelta(days=base_days_ago + offset),
            )

    def test_generate_product_insight_flags_stockout_risk(self):
        user = self._make_user(currency="NGN")
        product = self._make_product(user, estimated_quantity=2, last_verified_quantity=2)
        self._add_sales(product, [4, 4, 4], base_days_ago=1)

        result = generate_product_insight(product)

        self.assertTrue(result.should_notify)
        self.assertEqual(result.notification_type, "stockout_risk")
        self.assertIn("run out", result.message)
        self.assertGreater(result.potential_revenue_loss_weekly, 0)

    def test_generate_product_insight_flags_dead_stock(self):
        user = self._make_user()
        product = self._make_product(user, estimated_quantity=25, last_verified_quantity=25)
        Product.objects.filter(id=product.id).update(created_at=timezone.now() - timedelta(days=14))
        product.refresh_from_db()

        result = generate_product_insight(product)

        self.assertTrue(result.should_notify)
        self.assertEqual(result.notification_type, "dead_stock")
        self.assertIn("not moved", result.message)

    def test_generate_product_insight_flags_abnormal_drop(self):
        user = self._make_user()
        product = self._make_product(user, estimated_quantity=20, last_verified_quantity=20)
        self._add_sales(product, [6, 6, 6, 6, 6, 6, 6], base_days_ago=8)
        self._add_sales(product, [1, 1], base_days_ago=1)

        result = generate_product_insight(product)

        self.assertTrue(result.should_notify)
        self.assertEqual(result.notification_type, "drop")
        self.assertIn("fell", result.message)

    def test_send_notification_dedupes_same_type_reference(self):
        user = self._make_user()

        first = send_notification(
            user,
            "You may run out soon.",
            "stockout_risk",
            "product:123",
            severity="medium",
            title="Stockout risk",
        )
        second = send_notification(
            user,
            "You may run out soon.",
            "stockout_risk",
            "product:123",
            severity="medium",
            title="Stockout risk",
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(Notification.objects.filter(user=user, notification_type="stockout_risk").count(), 1)

    def test_evaluate_user_inactivity_generates_risk(self):
        user = self._make_user()
        self._make_product(user)
        self.user_model.objects.filter(id=user.id).update(last_login=timezone.now() - timedelta(days=3))
        user.refresh_from_db()

        result = evaluate_user_inactivity(user)

        self.assertTrue(result.should_notify)
        self.assertEqual(result.notification_type, "inactivity_risk")
        self.assertEqual(result.severity, "medium")

    @override_settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="hello@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="SiloXR <hello@example.com>",
    )
    @patch("apps.notifications.dispatch.send_mail", return_value=1)
    def test_inventory_event_signal_creates_notification(self, send_mail_mock):
        user = self._make_user()
        product = self._make_product(user, estimated_quantity=1, last_verified_quantity=1)
        self._add_sales(product, [5, 5, 5], base_days_ago=1)

        # Trigger a fresh event that will cause the signal to evaluate the product.
        InventoryEvent.objects.create(
            product=product,
            recorded_by=user,
            event_type=InventoryEvent.SALE,
            quantity=2,
            notes="signal test",
            occurred_at=timezone.now(),
        )

        self.assertTrue(Notification.objects.filter(user=user, notification_type="stockout_risk").exists())
        send_mail_mock.assert_called()

    @override_settings(
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_PORT=587,
        EMAIL_HOST_USER="hello@example.com",
        EMAIL_HOST_PASSWORD="secret",
        DEFAULT_FROM_EMAIL="SiloXR <hello@example.com>",
    )
    @patch("apps.notifications.management.commands.run_proactive_checks.notify_user")
    def test_run_proactive_checks_invokes_product_and_inactivity_paths(self, notify_mock):
        notify_mock.return_value = NotificationDispatchResult(notification=None, created=True)
        user = self._make_user()
        product = self._make_product(user, estimated_quantity=2, last_verified_quantity=2)
        self._add_sales(product, [4, 4, 4], base_days_ago=1)
        self.user_model.objects.filter(id=user.id).update(last_login=timezone.now() - timedelta(days=3))
        user.refresh_from_db()

        result = run_proactive_checks(user_limit=1)

        self.assertEqual(result.users_processed, 1)
        self.assertGreaterEqual(result.notifications_created + result.inactivity_notifications, 1)
        self.assertTrue(notify_mock.called)
