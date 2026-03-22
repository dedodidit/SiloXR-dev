# backend/apps/inventory/events.py

import logging
from datetime import datetime, timezone as dt_tz
from typing import Optional
from django.db import transaction
from django.utils import timezone

from .models import Product, InventoryEvent

logger = logging.getLogger(__name__)


class EventProcessingError(Exception):
    pass


class EventProcessor:
    """
    The single entry point for all inventory state changes.

    Usage:
        processor = EventProcessor(product)
        event = processor.record(
            event_type=InventoryEvent.SALE,
            quantity=5,
            occurred_at=datetime.now(),
            recorded_by=request.user,
        )

    This class enforces:
    1. Every change is logged as an InventoryEvent (time-series)
    2. STOCK_COUNT events update last_verified_quantity, NOT estimated_quantity
    3. estimated_quantity is updated by applying signed delta
    4. Duplicate offline events are rejected via client_event_id
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
        All writes are atomic — partial state is never committed.
        """
        if occurred_at is None:
            occurred_at = timezone.now()

        # Deduplicate offline syncs
        if client_event_id:
            existing = InventoryEvent.objects.filter(
                client_event_id=client_event_id
            ).first()
            if existing:
                logger.info(
                    "Duplicate offline event rejected: client_event_id=%s", client_event_id
                )
                return existing

        # Validate event type
        valid_types = {t[0] for t in InventoryEvent.EVENT_TYPE_CHOICES}
        if event_type not in valid_types:
            raise EventProcessingError(f"Unknown event type: {event_type}")

        # STOCK_COUNT requires verified_quantity
        if event_type == InventoryEvent.STOCK_COUNT and verified_quantity is None:
            raise EventProcessingError(
                "STOCK_COUNT events require verified_quantity."
            )

        # Create the event record
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

        # Update product state based on event type
        self._apply_event_to_product(event)

        logger.info(
            "Event recorded: %s × %.2f for %s (offline=%s)",
            event_type,
            quantity,
            self.product.sku,
            is_offline_event,
        )

        return event

    def _apply_event_to_product(self, event: InventoryEvent) -> None:
        """
        Apply the event's effect to the product's state fields.

        KEY INVARIANT:
        - STOCK_COUNT → updates last_verified_quantity + last_verified_at
                        resets confidence because we now have ground truth
        - All others  → updates estimated_quantity via signed delta
                        may lower confidence if event is unexpected
        """
        product = self.product

        if event.event_type == InventoryEvent.STOCK_COUNT:
            # Ground truth received — update verified fields
            product.last_verified_quantity = event.verified_quantity
            product.last_verified_at = event.occurred_at
            # Snap estimated to verified and reset confidence to high
            product.estimated_quantity = float(event.verified_quantity)
            product.confidence_score = 0.9  # High confidence after physical count
        else:
            # Apply signed delta to estimated quantity
            delta = event.signed_quantity
            product.estimated_quantity = max(0.0, product.estimated_quantity + delta)

            # Decay confidence slightly for each unverified event
            # The Learning Engine will recalculate this properly later
            product.confidence_score = max(
                0.1,
                product.confidence_score * 0.98,
            )

        product.save(
            update_fields=[
                "estimated_quantity",
                "last_verified_quantity",
                "last_verified_at",
                "confidence_score",
                "updated_at",
            ]
        )