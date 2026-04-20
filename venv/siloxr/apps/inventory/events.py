# backend/apps/inventory/events.py

import logging
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone

from .models import InventoryEvent, Product

logger = logging.getLogger(__name__)


class EventProcessingError(Exception):
    pass


class EventProcessor:
    """
    Single entry point for inventory state changes.

    Every change is written as an InventoryEvent and the product's
    running state is updated inside the same transaction.
    """

    def __init__(self, product: Product):
        self.product = product

    @transaction.atomic
    def record(
        self,
        event_type: str,
        quantity: float,
        occurred_at: Optional[datetime] = None,
        recorded_by=None,
        notes: str = "",
        verified_quantity: Optional[int] = None,
        client_event_id=None,
        is_offline_event: bool = False,
    ) -> InventoryEvent:
        """
        Record an inventory event and update product state accordingly.
        """
        if occurred_at is None:
            occurred_at = timezone.now()

        if client_event_id:
            existing = InventoryEvent.objects.filter(client_event_id=client_event_id).first()
            if existing:
                logger.info("Duplicate offline event rejected: client_event_id=%s", client_event_id)
                return existing

        valid_types = {choice[0] for choice in InventoryEvent.EVENT_TYPE_CHOICES}
        if event_type not in valid_types:
            raise EventProcessingError(f"Unknown event type: {event_type}")

        if event_type == InventoryEvent.STOCK_COUNT and verified_quantity is None:
            raise EventProcessingError("STOCK_COUNT events require verified_quantity.")

        event = InventoryEvent(
            product=self.product,
            recorded_by=recorded_by,
            event_type=event_type,
            quantity=quantity,
            verified_quantity=verified_quantity,
            notes=notes,
            is_offline_event=is_offline_event,
            client_event_id=client_event_id,
            occurred_at=occurred_at,
        )
        event.save()

        self._apply_event_to_product(event)
        self._queue_insight_notification(event)

        logger.info(
            "Event recorded: %s x %.2f for %s (offline=%s)",
            event_type,
            quantity,
            self.product.sku,
            is_offline_event,
        )

        return event

    def _queue_insight_notification(self, event: InventoryEvent) -> None:
        def _notify():
            try:
                from apps.notifications.services.insight_engine import generate_product_insight
                from apps.notifications.services.notification_service import notify_user

                insight = generate_product_insight(event.product_id)
                if insight.should_notify:
                    notify_user(
                        self.product.owner,
                        insight.message,
                        insight.notification_type,
                        insight.reference_id,
                        severity=insight.severity,
                        title=insight.title,
                        metadata=insight.metadata,
                    )
            except Exception as exc:
                logger.warning(
                    "Product insight notification failed for %s: %s",
                    self.product.sku,
                    exc,
                    exc_info=True,
                )

        transaction.on_commit(_notify)

    def _apply_event_to_product(self, event: InventoryEvent) -> None:
        """
        Apply the event's effect to the product's state fields.
        """
        product = self.product

        if event.event_type == InventoryEvent.STOCK_COUNT:
            product.last_verified_quantity = event.verified_quantity
            product.last_verified_at = event.occurred_at
            product.estimated_quantity = float(event.verified_quantity)
            product.confidence_score = 0.9
        else:
            delta = event.signed_quantity
            product.estimated_quantity = max(0.0, product.estimated_quantity + delta)
            product.confidence_score = max(0.1, product.confidence_score * 0.98)

        product.save(
            update_fields=[
                "estimated_quantity",
                "last_verified_quantity",
                "last_verified_at",
                "confidence_score",
                "updated_at",
            ]
        )
