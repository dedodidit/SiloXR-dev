from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction

from apps.inventory.models import InventoryEvent
from apps.notifications.services.insight_engine import generate_product_insight
from apps.notifications.services.notification_service import notify_user

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InventoryEvent)
def handle_inventory_event_notifications(sender, instance: InventoryEvent, created: bool, **kwargs):
    if not created:
        return

    def _dispatch():
        try:
            insight = generate_product_insight(instance.product_id)
            if insight.should_notify:
                notify_user(
                    instance.product.owner,
                    insight.message,
                    insight.notification_type,
                    insight.reference_id,
                    severity=insight.severity,
                    title=insight.title,
                    metadata=insight.metadata,
                )
        except Exception as exc:
            logger.warning(
                "Inventory event notification dispatch failed for %s: %s",
                instance.id,
                exc,
                exc_info=True,
            )

    transaction.on_commit(_dispatch)
