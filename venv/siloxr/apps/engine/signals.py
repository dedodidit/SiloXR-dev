# backend/apps/engine/signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.billing.enums import FeatureFlag
from apps.billing.services import FeatureGateService
from apps.inventory.models import BurnRate, ForecastSnapshot, InventoryEvent

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InventoryEvent)
def trigger_learning_on_event(
    sender, instance: InventoryEvent, created: bool, **kwargs
):
    """
    InventoryEvent (SALE | STOCK_COUNT)
      → Learning Engine → BurnRate (triggers next signal)
    """
    if not created:
        return

    if instance.event_type not in {InventoryEvent.SALE, InventoryEvent.STOCK_COUNT}:
        return

    try:
        from apps.engine.learning import LearningEngine
        LearningEngine().run(instance.product)
    except Exception as exc:
        logger.error(
            "Learning failed after event %s: %s",
            instance.id, exc, exc_info=True,
        )


@receiver(post_save, sender=BurnRate)
def trigger_forecast_on_burn_rate(
    sender, instance: BurnRate, created: bool, **kwargs
):
    """
    BurnRate (new)
      → Forecast Engine → ForecastSnapshot (triggers next signal)
    """
    if not created:
        return

    try:
        from apps.engine.forecast import ForecastEngine
        ForecastEngine().run(instance.product)
    except Exception as exc:
        logger.error(
            "Forecast failed after BurnRate %s: %s",
            instance.id, exc, exc_info=True,
        )


@receiver(post_save, sender=ForecastSnapshot)
def trigger_decision_on_forecast(
    sender, instance: ForecastSnapshot, created: bool, **kwargs
):
    """
    ForecastSnapshot (new)
      → Decision Engine → DecisionLog → Notification

    Gate: only runs for plans with action-layer access.
    Free users' products are learned and forecasted but not decided.
    """
    if not created:
        return

    product = instance.product

    if not FeatureGateService.has_access(product.owner.current_plan, FeatureFlag.VIEW_ACTIONS):
        logger.debug(
            "Decision skipped for %s because the current plan has no action access", product.sku
        )
        return

    # Debounce: only run once per product per minute.
    # A 30-day forecast writes up to 22 snapshots — without this,
    # the decision engine would run 22 times in one second.
    from django.core.cache import cache
    debounce_key = f"decision_debounce_{product.id}"
    if cache.get(debounce_key):
        return
    cache.set(debounce_key, True, timeout=60)

    try:
        from apps.engine.forecast import ForecastEngine
        from apps.engine.decision import DecisionEngine
        from apps.inventory.models import DecisionLog

        forecast = ForecastEngine().run(product)
        output   = DecisionEngine().run(product, forecast)

        # Dispatch in-app notification for all actionable decisions
        if output and not output.skipped and output.action != DecisionLog.HOLD:
            try:
                log = DecisionLog.objects.get(id=output.decision_log_id)
                from apps.notifications.dispatch import dispatch_decision_notification
                dispatch_decision_notification(log)
            except Exception as exc:
                logger.error(
                    "Notification dispatch failed for %s: %s",
                    product.sku, exc, exc_info=True,
                )

        try:
            from apps.engine.insights import InsightEngine
            from apps.notifications.dispatch import dispatch_insight_notifications

            insights = InsightEngine().run(product, product.owner)
            if insights:
                dispatch_insight_notifications(product, insights)
        except Exception as exc:
            logger.error(
                "InsightEngine failed for %s: %s",
                product.sku, exc, exc_info=True,
            )

    except Exception as exc:
        logger.error(
            "Decision failed after ForecastSnapshot %s: %s",
            instance.id, exc, exc_info=True,
        )
