# backend/apps/api/tests/test_api.py

from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.models import NigeriaBaselineProduct
from apps.inventory.models import BurnRate, DecisionLog, ForecastSnapshot, Product
from apps.inventory.events import EventProcessor


class APITestBase(APITestCase):

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.free_user = User.objects.create_user(
            username="free", email="free@siloxr.com",
            password="pass", tier="free",
        )
        self.pro_user = User.objects.create_user(
            username="pro", email="pro@siloxr.com",
            password="pass", tier="pro",
        )
        self.product = Product.objects.create(
            owner=self.pro_user,
            name="API Widget",
            sku="API-001",
            estimated_quantity=100.0,
            last_verified_quantity=100,
            reorder_point=20,
        )

    def auth_free(self):
        self.client.force_authenticate(user=self.free_user)

    def auth_pro(self):
        self.client.force_authenticate(user=self.pro_user)


class TestProductEndpoints(APITestBase):

    def test_list_returns_own_products_only(self):
        self.auth_pro()
        resp = self.client.get("/api/v1/products/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        skus = [p["sku"] for p in resp.data["results"]]
        self.assertIn("API-001", skus)

    def test_other_users_product_not_visible(self):
        self.auth_free()
        resp = self.client.get("/api/v1/products/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["count"], 0)

    def test_create_product(self):
        self.auth_pro()
        resp = self.client.post("/api/v1/products/", {
            "name": "New Product", "sku": "NEW-001", "unit": "kg",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["sku"], "NEW-001")

    def test_duplicate_sku_rejected(self):
        self.auth_pro()
        self.client.post("/api/v1/products/", {"name": "X", "sku": "DUP-001"})
        resp = self.client.post("/api/v1/products/", {"name": "Y", "sku": "DUP-001"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_record_event_via_product_action(self):
        self.auth_pro()
        url  = f"/api/v1/products/{self.product.id}/events/"
        resp = self.client.post(url, {
            "event_type": "SALE",
            "quantity":   10,
            "occurred_at": timezone.now().isoformat(),
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["event_type"], "SALE")

    def test_stock_count_event_requires_verified_quantity(self):
        self.auth_pro()
        url  = f"/api/v1/products/{self.product.id}/events/"
        resp = self.client.post(url, {
            "event_type": "STOCK_COUNT",
            "quantity":   0,
            "occurred_at": timezone.now().isoformat(),
            # verified_quantity intentionally omitted
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_preserves_event_history(self):
        self.auth_pro()
        processor = EventProcessor(self.product)
        processor.record(
            event_type="SALE", quantity=5,
            occurred_at=timezone.now(), recorded_by=self.pro_user,
        )
        self.client.delete(f"/api/v1/products/{self.product.id}/")
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)
        # Events still exist
        self.assertTrue(self.product.events.exists())


class TestDecisionEndpoints(APITestBase):

    def _make_decision(self, action=DecisionLog.ALERT_LOW):
        return DecisionLog.objects.create(
            product=self.product,
            action=action,
            reasoning="Test reasoning with confidence 65%.",
            confidence_score=0.65,
            estimated_quantity_at_decision=80.0,
            expires_at=timezone.now() + timedelta(hours=12),
        )

    def test_decisions_require_pro(self):
        self.auth_free()
        resp = self.client.get("/api/v1/decisions/")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_pro_user_can_list_decisions(self):
        self.auth_pro()
        self._make_decision()
        resp = self.client.get("/api/v1/decisions/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreater(resp.data["count"], 0)

    def test_acknowledge_decision(self):
        self.auth_pro()
        decision = self._make_decision()
        url  = f"/api/v1/decisions/{decision.id}/acknowledge/"
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        decision.refresh_from_db()
        self.assertTrue(decision.is_acknowledged)

    def test_acknowledged_decision_excluded_from_active_list(self):
        self.auth_pro()
        decision = self._make_decision()
        decision.is_acknowledged = True
        decision.acknowledged_at = timezone.now()
        decision.save()
        resp = self.client.get("/api/v1/decisions/?active=true")
        ids  = [d["id"] for d in resp.data["results"]]
        self.assertNotIn(str(decision.id), ids)

    def test_decision_response_includes_reasoning(self):
        self.auth_pro()
        self._make_decision()
        resp = self.client.get("/api/v1/decisions/")
        first = resp.data["results"][0]
        self.assertIn("reasoning", first)
        self.assertIn("confidence_score", first)
        self.assertIn("confidence_label", first)
        self.assertIn("severity", first)

    def test_pro_error_response_is_structured(self):
        self.auth_free()
        resp = self.client.get("/api/v1/decisions/")
        self.assertIn("error", resp.data)
        self.assertEqual(resp.data["error"], "pro_required")


class TestDashboardEndpoints(APITestBase):

    def test_summary_returns_for_free_user(self):
        self.auth_free()
        resp = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("total_products", resp.data)
        self.assertIsNone(resp.data["active_decisions"])

    def test_summary_includes_decisions_for_pro(self):
        self.auth_pro()
        DecisionLog.objects.create(
            product=self.product,
            action=DecisionLog.REORDER,
            reasoning="Reorder suggested. Confidence 71%.",
            confidence_score=0.71,
            estimated_quantity_at_decision=25.0,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        resp = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp.data["active_decisions"])
        self.assertTrue(resp.data["is_pro"])

    def test_health_endpoint_no_auth_required(self):
        resp = self.client.get("/api/v1/dashboard/health/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("status", resp.data)


class TestBusinessHealthEndpoints(APITestBase):

    def test_summary_returns_structured_business_health_report(self):
        self.auth_pro()
        self.product.name = "Coca-Cola 50cl PET"
        self.product.selling_price = 300
        self.product.confidence_score = 0.72
        self.product.category = "beverages"
        self.product.save(update_fields=["name", "selling_price", "confidence_score", "category"])

        BurnRate.objects.create(
            product=self.product,
            burn_rate_per_day=5.0,
            burn_rate_std_dev=1.0,
            sample_event_count=8,
            confidence_score=0.76,
            window_days=30,
        )
        NigeriaBaselineProduct.objects.create(
            country="nigeria",
            industry="retail",
            category="beverages",
            generic_category="carbonated_soft_drink",
            product_name="Coca-Cola 50cl PET",
            unit_type="unit",
            weekly_turnover_low=30.0,
            weekly_turnover_high=42.0,
            avg_weekly_turnover=35.0,
            demand_std=4.0,
            daily_demand=5.0,
            avg_unit_price=300.0,
            cv_estimate=0.2,
            lead_time_days=2,
            source="test_fixture",
        )

        resp = self.client.get("/api/v1/business-health/summary/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("summary", resp.data)
        self.assertIn("top_products", resp.data)
        self.assertIn("demand_gaps", resp.data)
        self.assertIn("investor_summary", resp.data)
        self.assertEqual(resp.data["summary"]["estimated_weekly_revenue"], 10500.0)
        self.assertGreaterEqual(resp.data["summary"]["potential_revenue_gap_weekly"], 0.0)
        self.assertEqual(resp.data["top_products"][0]["name"], "Coca-Cola 50cl PET")


class TestTelegramLinkEndpoint(APITestBase):

    @override_settings(TELEGRAM_BOT_USERNAME=12345)
    def test_telegram_link_handles_non_string_bot_username(self):
        self.auth_pro()

        resp = self.client.get("/api/v1/telegram/link/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["bot_user"], "12345")
        self.assertIn("https://t.me/12345?start=", resp.data["link"])

    @override_settings(TELEGRAM_BOT_USERNAME=None)
    def test_telegram_link_returns_503_when_bot_username_missing(self):
        self.auth_pro()

        resp = self.client.get("/api/v1/telegram/link/")

        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["detail"], "Telegram linking is not configured yet.")


class TestOfflineSync(APITestBase):

    def test_bulk_sync_creates_events(self):
        self.auth_pro()
        resp = self.client.post("/api/v1/events/sync/bulk/", {
            "events": [
                {
                    "product_id":      str(self.product.id),
                    "event_type":      "SALE",
                    "quantity":        5,
                    "occurred_at":     timezone.now().isoformat(),
                    "client_event_id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "is_offline_event": True,
                }
            ]
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(resp.data["summary"]["succeeded"], 1)

    def test_duplicate_client_event_id_skipped(self):
        self.auth_pro()
        payload = {
            "events": [{
                "product_id":       str(self.product.id),
                "event_type":       "SALE",
                "quantity":         5,
                "occurred_at":      timezone.now().isoformat(),
                "client_event_id":  "bbbbbbbb-0000-0000-0000-000000000002",
                "is_offline_event": True,
            }]
        }
        self.client.post("/api/v1/events/sync/bulk/", payload, format="json")
        # Send again with the same client_event_id
        resp = self.client.post("/api/v1/events/sync/bulk/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertIn(
            resp.data["summary"]["skipped"] + resp.data["summary"]["succeeded"],
            [1],
        )

    def test_partial_failure_returns_207(self):
        self.auth_pro()
        resp = self.client.post("/api/v1/events/sync/bulk/", {
            "events": [
                {
                    "product_id":      str(self.product.id),
                    "event_type":      "SALE",
                    "quantity":        3,
                    "occurred_at":     timezone.now().isoformat(),
                    "client_event_id": "cccccccc-0000-0000-0000-000000000003",
                },
                {
                    "product_id":      "00000000-0000-0000-0000-000000000000",
                    "event_type":      "SALE",
                    "quantity":        3,
                    "occurred_at":     timezone.now().isoformat(),
                    "client_event_id": "cccccccc-0000-0000-0000-000000000004",
                },
            ]
        }, format="json")
        self.assertEqual(resp.status_code, status.HTTP_207_MULTI_STATUS)
        self.assertEqual(resp.data["summary"]["succeeded"], 1)
        self.assertEqual(resp.data["summary"]["failed"],    1)


class TestRegistrationAndUpload(APITestBase):

    def test_register_persists_country_and_currency(self):
        resp = self.client.post("/api/v1/auth/register/", {
            "username": "global-owner",
            "email": "global-owner@example.com",
            "password": "SecurePass123!",
            "business_name": "Global Foods Ltd",
            "business_type": "retail",
            "country": "ghana",
            "currency": "GHS",
            "terms_accepted": True,
            "terms_version": "test-v1",
        }, format="json")

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["country"], "ghana")
        self.assertEqual(resp.data["currency"], "GHS")

    def test_free_uploads_over_1mb_are_rejected(self):
        self.auth_free()
        oversized = SimpleUploadedFile(
            "sales.csv",
            b"a" * (1024 * 1024 + 1),
            content_type="text/csv",
        )

        resp = self.client.post("/api/v1/upload/", {
            "file": oversized,
            "default_event_type": "SALE",
        })

        self.assertEqual(resp.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

    def test_pro_uploads_over_1mb_can_continue_to_validation(self):
        self.auth_pro()
        oversized = SimpleUploadedFile(
            "sales.csv",
            b"a" * (1024 * 1024 + 1),
            content_type="text/csv",
        )

        resp = self.client.post("/api/v1/upload/", {
            "file": oversized,
            "default_event_type": "SALE",
        })

        self.assertNotEqual(resp.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
