from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Product
from apps.notifications.models import Notification, NotificationThrottle, TelegramProfile
from apps.notifications.reminders import send_product_update_reminders
from apps.notifications.router import NotificationRouter


class ProductUpdateReminderTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

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
        user = self._make_user()
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.email)
        self.assertFalse(result.telegram)
        self.assertEqual(Notification.objects.filter(user=user).count(), 1)
        self.assertTrue(
            NotificationThrottle.objects.filter(user=user, channel="upd_reminder").exists()
        )
        send_mail_mock.assert_called_once()

    @patch("apps.notifications.telegram.send_product_update_reminder", return_value=True)
    @patch("apps.notifications.dispatch.send_mail")
    def test_route_product_update_reminder_prefers_telegram(self, send_mail_mock, telegram_mock):
        user = self._make_user(preferred_channel="telegram", telegram_enabled=True)
        TelegramProfile.objects.create(user=user, chat_id=123456789, username="tester", is_active=True)
        product = self._make_product(user)

        result = NotificationRouter().route_product_update_reminder(user, [product], cadence_hours=24)

        self.assertTrue(result.in_app)
        self.assertTrue(result.telegram)
        self.assertFalse(result.email)
        telegram_mock.assert_called_once()
        send_mail_mock.assert_not_called()

    @patch("apps.notifications.dispatch.send_mail")
    def test_send_product_update_reminders_respects_cadence(self, send_mail_mock):
        user = self._make_user()
        self._make_product(user, sku="SKU-ST-1")

        first = send_product_update_reminders(cadence_hours=24)
        second = send_product_update_reminders(cadence_hours=24)

        self.assertEqual(first.users_notified, 1)
        self.assertEqual(second.users_notified, 0)
        self.assertEqual(Notification.objects.filter(user=user).count(), 1)
        send_mail_mock.assert_called_once()
