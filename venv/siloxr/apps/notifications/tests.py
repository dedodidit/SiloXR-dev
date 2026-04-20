from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.inventory.models import Product
from apps.notifications.models import Notification, NotificationThrottle, TelegramProfile
from apps.notifications.reminders import (
    maybe_send_automated_product_update_reminder,
    send_product_update_reminders,
)
from apps.notifications.dispatch import dispatch_dashboard_insights, _send_email_message, notification_channel_status
from apps.notifications.business_briefs import resolve_business_brief_type, send_business_briefs
from apps.notifications.router import NotificationRouter


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
            "telegram_enabled": False,
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
        self.assertFalse(result.telegram)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_IN_APP).count(), 1)
        self.assertEqual(Notification.objects.filter(user=user, channel=Notification.CHANNEL_EMAIL).count(), 1)
        self.assertTrue(
            NotificationThrottle.objects.filter(user=user, channel="upd_reminder").exists()
        )
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.telegram.send_product_update_reminder", return_value=True)
    @patch("apps.notifications.dispatch.send_mail")
    def test_route_product_update_reminder_sends_both_ready_channels(self, send_mail_mock, telegram_mock):
        send_mail_mock.return_value = 1
        user = self._make_user(preferred_channel="telegram", telegram_enabled=True)
        TelegramProfile.objects.create(user=user, chat_id=123456789, username="tester", is_active=True)
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.telegram)
        self.assertTrue(result.email)
        telegram_mock.assert_called_once()
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.telegram.send_product_update_reminder", return_value=True)
    @patch("apps.notifications.dispatch.send_mail")
    def test_route_product_update_reminder_sends_email_even_when_telegram_is_preferred(self, send_mail_mock, telegram_mock):
        send_mail_mock.return_value = 1
        user = self._make_user(preferred_channel="telegram", telegram_enabled=True)
        TelegramProfile.objects.create(user=user, chat_id=123456789, username="tester", is_active=True)
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.telegram)
        self.assertTrue(result.email)
        telegram_mock.assert_called_once()
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

    @override_settings(
        TELEGRAM_BOT_USERNAME="SiloXRbot",
        TELEGRAM_BOT_TOKEN="token",
    )
    def test_notification_channel_status_reports_telegram_configuration(self):
        user = self._make_user(preferred_channel="telegram", telegram_enabled=True)
        TelegramProfile.objects.create(user=user, chat_id=999999999, username="tester", is_active=True)

        status = notification_channel_status(user)

        self.assertTrue(status["telegram"]["configured"])
        self.assertTrue(status["telegram"]["ready"])
        self.assertEqual(status["recommended_channel"], "telegram")

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
