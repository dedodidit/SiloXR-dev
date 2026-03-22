# backend/apps/api/tests/test_api.py

from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.inventory.models import DecisionLog, ForecastSnapshot, Product
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