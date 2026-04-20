from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from contextlib import contextmanager

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone

from apps.core.models import OTPVerification
from apps.engine import signals as engine_signals
from apps.engine.decision import DecisionEngine
from apps.engine.forecast import ForecastEngine
from apps.inventory.events import EventProcessor
from apps.inventory.models import (
    BurnRate,
    DecisionLog,
    ForecastSnapshot,
    InsightFeedback,
    InventoryEvent,
    Product,
    UserBehaviorLog,
)
from apps.notifications.dispatch import _build_body, _build_title
from apps.notifications.models import Notification, NotificationThrottle


@dataclass(frozen=True)
class ProductSeed:
    name: str
    sku: str
    category: str
    unit: str
    reorder_point: int
    reorder_quantity: int
    selling_price: Decimal
    opening_count: int
    supplier_note: str
    event_plan: list[dict]


class Command(BaseCommand):
    help = "Create or refresh a fully populated showcase account for dashboard demos."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="showcase.pro@siloxr.local")
        parser.add_argument("--username", default="showcasepro")
        parser.add_argument("--password", default="DemoPass123!")
        parser.add_argument("--business-name", default="TestPro Corner Shop")

    @transaction.atomic
    def handle(self, *args, **options):
        with self._signals_suspended():
            user = self._create_or_update_user(options)
            self._reset_showcase_data(user)

            products = self._seed_products(user)
            self._seed_burn_rates(products)
            live_decisions = self._refresh_decisions(products)
            timeline_decisions = self._seed_decision_timeline(user, live_decisions)
            self._seed_feedback_and_behavior(user, live_decisions, timeline_decisions)
            self._seed_notifications(user, live_decisions, timeline_decisions)

        self.stdout.write(self.style.SUCCESS("Showcase account ready."))
        self.stdout.write(f"Email: {user.email}")
        self.stdout.write(f"Username: {user.username}")
        self.stdout.write(f"Password: {options['password']}")
        self.stdout.write(f"Products: {Product.objects.filter(owner=user).count()}")
        self.stdout.write(
            f"Active decisions: {DecisionLog.objects.filter(product__owner=user, is_acknowledged=False).count()}"
        )
        self.stdout.write(
            f"Notifications: {Notification.objects.filter(user=user).count()}"
        )

    @contextmanager
    def _signals_suspended(self):
        post_save.disconnect(engine_signals.trigger_learning_on_event, sender=InventoryEvent)
        post_save.disconnect(engine_signals.trigger_forecast_on_burn_rate, sender=BurnRate)
        post_save.disconnect(engine_signals.trigger_decision_on_forecast, sender=ForecastSnapshot)
        try:
            yield
        finally:
            post_save.connect(engine_signals.trigger_learning_on_event, sender=InventoryEvent)
            post_save.connect(engine_signals.trigger_forecast_on_burn_rate, sender=BurnRate)
            post_save.connect(engine_signals.trigger_decision_on_forecast, sender=ForecastSnapshot)

    def _create_or_update_user(self, options):
        User = get_user_model()
        email = options["email"].strip().lower()
        username = options["username"].strip()
        password = options["password"]

        user, _ = User.objects.update_or_create(
            email=email,
            defaults={
                "username": username,
                "first_name": "Test",
                "last_name": "Pro",
                "business_name": options["business_name"],
                "business_type": "retail",
                "phone_number": "+2348012345678",
                "avatar_url": "",
                "tier": User.TIER_PRO,
                "tier_expires_at": timezone.now() + timedelta(days=180),
                "whatsapp_enabled": True,
                "whatsapp_critical_only": False,
                "email_notifications_enabled": True,
                "is_active": True,
            },
        )
        user.set_password(password)
        user.save(update_fields=["password"])
        return user

    def _reset_showcase_data(self, user):
        Notification.objects.filter(user=user).delete()
        NotificationThrottle.objects.filter(user=user).delete()
        UserBehaviorLog.objects.filter(user=user).delete()
        InsightFeedback.objects.filter(user=user).delete()
        OTPVerification.objects.filter(user=user).delete()
        Product.objects.filter(owner=user).delete()

    def _seed_products(self, user):
        now = timezone.now()
        seeds = [
            ProductSeed(
                name="Coke",
                sku="SKU-COKE-001",
                category="Beverages",
                unit="bottles",
                reorder_point=18,
                reorder_quantity=60,
                selling_price=Decimal("1200.00"),
                opening_count=54,
                supplier_note="Metro Drinks Ltd.",
                event_plan=[
                    {"days": 13, "type": InventoryEvent.SALE, "quantity": 6},
                    {"days": 11, "type": InventoryEvent.SALE, "quantity": 5},
                    {"days": 9, "type": InventoryEvent.SALE, "quantity": 7},
                    {"days": 6, "type": InventoryEvent.SALE, "quantity": 8},
                    {"days": 4, "type": InventoryEvent.SALE, "quantity": 9},
                    {"days": 2, "type": InventoryEvent.SALE, "quantity": 10},
                    {"days": 1, "type": InventoryEvent.SALE, "quantity": 7},
                ],
            ),
            ProductSeed(
                name="Bread",
                sku="SKU-BREAD-002",
                category="Bakery",
                unit="loaves",
                reorder_point=14,
                reorder_quantity=40,
                selling_price=Decimal("900.00"),
                opening_count=38,
                supplier_note="Daily Oven Suppliers",
                event_plan=[
                    {"days": 10, "type": InventoryEvent.SALE, "quantity": 4},
                    {"days": 8, "type": InventoryEvent.SALE, "quantity": 5},
                    {"days": 6, "type": InventoryEvent.SALE, "quantity": 4},
                    {"days": 4, "type": InventoryEvent.RESTOCK, "quantity": 6},
                    {"days": 3, "type": InventoryEvent.SALE, "quantity": 7},
                    {"days": 2, "type": InventoryEvent.SALE, "quantity": 5},
                    {"days": 1, "type": InventoryEvent.SALE, "quantity": 6},
                ],
            ),
            ProductSeed(
                name="Milk",
                sku="SKU-MILK-003",
                category="Dairy",
                unit="packs",
                reorder_point=10,
                reorder_quantity=30,
                selling_price=Decimal("1500.00"),
                opening_count=42,
                supplier_note="FreshDairy Hub",
                event_plan=[
                    {"days": 9, "type": InventoryEvent.SALE, "quantity": 2},
                    {"days": 7, "type": InventoryEvent.SALE, "quantity": 3},
                    {"days": 5, "type": InventoryEvent.SALE, "quantity": 2},
                    {"days": 3, "type": InventoryEvent.RESTOCK, "quantity": 12},
                    {"days": 2, "type": InventoryEvent.SALE, "quantity": 2},
                    {"days": 1, "type": InventoryEvent.SALE, "quantity": 3},
                ],
            ),
            ProductSeed(
                name="Rice",
                sku="SKU-RICE-004",
                category="Staples",
                unit="bags",
                reorder_point=8,
                reorder_quantity=24,
                selling_price=Decimal("42000.00"),
                opening_count=16,
                supplier_note="Lagos Grain Partners",
                event_plan=[
                    {"days": 18, "type": InventoryEvent.SALE, "quantity": 1},
                    {"days": 12, "type": InventoryEvent.SALE, "quantity": 2},
                    {"days": 5, "type": InventoryEvent.SALE, "quantity": 1},
                    {"days": 2, "type": InventoryEvent.WASTE, "quantity": 1},
                ],
            ),
            ProductSeed(
                name="Battery Pack",
                sku="SKU-BATT-005",
                category="Utilities",
                unit="packs",
                reorder_point=12,
                reorder_quantity=50,
                selling_price=Decimal("3500.00"),
                opening_count=33,
                supplier_note="Powerline Wholesale",
                event_plan=[
                    {"days": 12, "type": InventoryEvent.SALE, "quantity": 3},
                    {"days": 9, "type": InventoryEvent.SALE, "quantity": 4},
                    {"days": 6, "type": InventoryEvent.SALE, "quantity": 3},
                    {"days": 3, "type": InventoryEvent.SALE, "quantity": 5},
                    {"days": 1, "type": InventoryEvent.SALE, "quantity": 4},
                ],
            ),
        ]

        products: list[Product] = []
        for seed in seeds:
            product = Product.objects.create(
                owner=user,
                name=seed.name,
                sku=seed.sku,
                category=seed.category,
                unit=seed.unit,
                reorder_point=seed.reorder_point,
                reorder_quantity=seed.reorder_quantity,
                selling_price=seed.selling_price,
            )

            processor = EventProcessor(product)
            processor.record(
                event_type=InventoryEvent.STOCK_COUNT,
                quantity=0,
                verified_quantity=seed.opening_count,
                occurred_at=now - timedelta(days=max(14, len(seed.event_plan) + 2)),
                recorded_by=user,
                notes=f"Initial seeded stock count from {seed.supplier_note}",
            )

            for event in seed.event_plan:
                processor.record(
                    event_type=event["type"],
                    quantity=event["quantity"],
                    occurred_at=now - timedelta(days=event["days"]),
                    recorded_by=user,
                    notes=f"Seeded {event['type'].lower()} event for showcase account",
                )

            products.append(Product.objects.get(pk=product.pk))

        return products

    def _seed_burn_rates(self, products: list[Product]):
        seeds = {
            "SKU-COKE-001": {"rate": 7.6, "std": 1.8, "confidence": 0.84, "sample_days": 14, "events": 7},
            "SKU-BREAD-002": {"rate": 4.2, "std": 1.1, "confidence": 0.74, "sample_days": 12, "events": 6},
            "SKU-MILK-003": {"rate": 1.9, "std": 0.4, "confidence": 0.81, "sample_days": 9, "events": 5},
            "SKU-RICE-004": {"rate": 0.8, "std": 0.55, "confidence": 0.31, "sample_days": 18, "events": 4},
            "SKU-BATT-005": {"rate": 3.8, "std": 1.3, "confidence": 0.69, "sample_days": 12, "events": 5},
        }

        for product in products:
            seed = seeds[product.sku]
            BurnRate.objects.create(
                product=product,
                burn_rate_per_day=seed["rate"],
                burn_rate_std_dev=seed["std"],
                confidence_score=seed["confidence"],
                sample_days=seed["sample_days"],
                sample_event_count=seed["events"],
                window_days=30,
            )
            Product.objects.filter(pk=product.pk).update(confidence_score=seed["confidence"])

    def _refresh_decisions(self, products: list[Product]) -> list[DecisionLog]:
        forecast_engine = ForecastEngine()
        decision_engine = DecisionEngine()

        live_decisions: list[DecisionLog] = []
        for product in products:
            forecast = forecast_engine.run(product)
            output = decision_engine.run(product, forecast)
            if output.skipped or not output.decision_log_id:
                continue
            decision = DecisionLog.objects.get(pk=output.decision_log_id)
            live_decisions.append(decision)

        if live_decisions:
            live_decisions[0].mark_viewed()

        return live_decisions

    def _seed_decision_timeline(self, user, live_decisions: list[DecisionLog]) -> list[DecisionLog]:
        historical: list[DecisionLog] = []
        if not live_decisions:
            return historical

        base = live_decisions[0]
        acted = self._clone_decision(base, created_offset_days=2)
        acted.mark_acted("prevented_stockout")
        historical.append(acted)

        source = live_decisions[1] if len(live_decisions) > 1 else base
        ignored = self._clone_decision(source, created_offset_days=4)
        ignored.mark_ignored()
        historical.append(ignored)

        viewed_source = live_decisions[2] if len(live_decisions) > 2 else base
        viewed = self._clone_decision(viewed_source, created_offset_days=1)
        viewed.mark_viewed()
        historical.append(viewed)

        return historical

    def _clone_decision(self, decision: DecisionLog, created_offset_days: int) -> DecisionLog:
        created_at = timezone.now() - timedelta(days=created_offset_days)
        clone = DecisionLog.objects.create(
            product=decision.product,
            forecast=decision.forecast,
            action=decision.action,
            reasoning=decision.reasoning,
            confidence_score=decision.confidence_score,
            estimated_quantity_at_decision=decision.estimated_quantity_at_decision,
            days_remaining_at_decision=decision.days_remaining_at_decision,
            burn_rate_at_decision=decision.burn_rate_at_decision,
            estimated_lost_sales=decision.estimated_lost_sales,
            estimated_revenue_loss=decision.estimated_revenue_loss,
            risk_score=decision.risk_score,
            priority_score=decision.priority_score,
            expires_at=created_at + timedelta(days=5),
        )
        DecisionLog.objects.filter(pk=clone.pk).update(created_at=created_at)
        clone.refresh_from_db()
        return clone

    def _seed_feedback_and_behavior(self, user, live_decisions, timeline_decisions):
        all_decisions = [*live_decisions, *timeline_decisions]
        if not all_decisions:
            return

        InsightFeedback.objects.create(
            user=user,
            decision=live_decisions[0],
            product=live_decisions[0].product,
            was_helpful=True,
            was_accurate=True,
            comment="This helped us catch low stock before the weekend rush.",
        )

        if len(all_decisions) > 1:
            InsightFeedback.objects.create(
                user=user,
                decision=all_decisions[1],
                product=all_decisions[1].product,
                was_helpful=False,
                was_accurate=False,
                comment="This one arrived late after we had already checked the shelf.",
            )

        for index, decision in enumerate(all_decisions[:4]):
            UserBehaviorLog.objects.create(
                user=user,
                product=decision.product,
                decision=decision,
                event_type=UserBehaviorLog.EVENT_DECISION_VIEWED,
                interaction_time_ms=1400 + (index * 260),
                product_update_frequency=2.5,
                metadata={"source": "showcase_seed", "decision_action": decision.action},
            )

        acted_decision = next((item for item in timeline_decisions if item.status == DecisionLog.STATUS_ACTED), None)
        if acted_decision:
            UserBehaviorLog.objects.create(
                user=user,
                product=acted_decision.product,
                decision=acted_decision,
                event_type=UserBehaviorLog.EVENT_DECISION_ACTED,
                interaction_time_ms=3100,
                product_update_frequency=3.2,
                metadata={"source": "showcase_seed", "outcome": acted_decision.outcome_label},
            )

        ignored_decision = next((item for item in timeline_decisions if item.status == DecisionLog.STATUS_IGNORED), None)
        if ignored_decision:
            UserBehaviorLog.objects.create(
                user=user,
                product=ignored_decision.product,
                decision=ignored_decision,
                event_type=UserBehaviorLog.EVENT_DECISION_IGNORED,
                interaction_time_ms=1800,
                product_update_frequency=1.3,
                metadata={"source": "showcase_seed"},
            )

        for product in Product.objects.filter(owner=user)[:3]:
            UserBehaviorLog.objects.create(
                user=user,
                product=product,
                event_type=UserBehaviorLog.EVENT_PRODUCT_UPDATED,
                interaction_time_ms=900,
                product_update_frequency=4.0,
                metadata={"source": "showcase_seed", "kind": "quick_action"},
            )

    def _seed_notifications(self, user, live_decisions, timeline_decisions):
        Notification.objects.filter(user=user).delete()

        for decision in live_decisions[:3]:
            Notification.objects.create(
                user=user,
                decision=decision,
                channel=Notification.CHANNEL_IN_APP,
                title=_build_title(decision),
                body=_build_body(decision),
                confidence=decision.confidence_score,
            )

        now = timezone.now()
        if len(live_decisions) > 1:
            Notification.objects.create(
                user=user,
                decision=live_decisions[1],
                channel=Notification.CHANNEL_EMAIL,
                title="Daily summary prepared",
                body="Milk remains stable, while Coke and Battery Pack need closer attention over the next few days.",
                confidence=live_decisions[1].confidence_score,
                is_read=True,
                read_at=now - timedelta(hours=8),
            )

        critical = next((item for item in live_decisions if item.severity == "critical"), None)
        if critical:
            Notification.objects.create(
                user=user,
                decision=critical,
                channel=Notification.CHANNEL_WHATSAPP,
                title=f"WhatsApp alert sent for {critical.product.name}",
                body=f"Recommendation: restock soon. Reasoning: {critical.reasoning}",
                confidence=critical.confidence_score,
            )
            NotificationThrottle.record(user, critical.product, "whatsapp")
