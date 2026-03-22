# backend/apps/engine/nudge.py

"""
Nudge Engine.

Generates minimal-friction prompts to increase data quality.
Never forces. Always assists.

Nudge types:
  binary  — yes/no question
  range   — ask for an approximate number
  confirm — confirm a system assumption

Trigger rules:
  - confidence < 0.4 → ask for a count
  - no sale events in 7 days → ask if product is still stocked
  - high conflict ratio → ask which signal is more reliable
  - stockout_flag → confirm stockout

NEVER expose internal calculations in nudge text.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class NudgeRequest:
    """
    A single nudge prompt to be shown to the user.
    Stored in DB and served via API.
    """
    product_id:   str
    product_name: str
    nudge_type:   str      # "binary" | "range" | "confirm"
    question:     str
    yes_label:    str = "Yes"
    no_label:     str  = "Not sure"
    range_min:    int  = 0
    range_max:    int  = 1000
    range_unit:   str  = "units"
    priority:     int  = 5   # 1 = highest
    trigger:      str  = ""  # what triggered this nudge


class NudgeEngine:
    """
    Evaluates product state and generates contextual nudge prompts.
    Called after the Signal Fusion Engine runs.
    """

    CONFIDENCE_NUDGE_FLOOR = 0.40
    STALE_SALE_DAYS        = 7
    MAX_ACTIVE_NUDGES      = 3   # never overwhelm the user

    def generate(self, product, fusion_result=None) -> list[NudgeRequest]:
        """
        Generate nudge prompts for a product.
        Returns a list ordered by priority (1 = show first).
        """
        nudges = []

        # 1. Low confidence → ask for a count
        if product.confidence_score < self.CONFIDENCE_NUDGE_FLOOR:
            nudges.append(NudgeRequest(
                product_id   = str(product.id),
                product_name = product.name,
                nudge_type   = "range",
                question     = f"Quick question — roughly how many {product.name} do you have right now?",
                range_min    = 0,
                range_max    = max(100, int(product.estimated_quantity * 3)),
                range_unit   = product.unit,
                priority     = 1,
                trigger      = "low_confidence",
            ))

        # 2. No recent sales → confirm product is still stocked
        from apps.inventory.models import InventoryEvent
        recent_sales = InventoryEvent.objects.filter(
            product    = product,
            event_type = InventoryEvent.SALE,
            occurred_at__gte = timezone.now() - timedelta(days=self.STALE_SALE_DAYS),
        ).exists()

        if not recent_sales and product.estimated_quantity > 0:
            nudges.append(NudgeRequest(
                product_id   = str(product.id),
                product_name = product.name,
                nudge_type   = "binary",
                question     = f"Do you still have {product.name} in stock?",
                yes_label    = "Yes, still have some",
                no_label     = "No, ran out",
                priority     = 2,
                trigger      = "no_recent_sales",
            ))

        # 3. Stockout flag → confirm
        if fusion_result and fusion_result.stockout_flag:
            nudges.append(NudgeRequest(
                product_id   = str(product.id),
                product_name = product.name,
                nudge_type   = "binary",
                question     = f"It looks like {product.name} may be out of stock. Can you confirm?",
                yes_label    = "Yes, out of stock",
                no_label     = "No, I have some",
                priority     = 1,
                trigger      = "stockout_suspected",
            ))

        # 4. Signal conflict → ask which data source to trust more
        if (
            fusion_result
            and fusion_result.conflict_ratio > 0.4
            and product.confidence_score < 0.6
        ):
            nudges.append(NudgeRequest(
                product_id   = str(product.id),
                product_name = product.name,
                nudge_type   = "binary",
                question     = f"Our data for {product.name} has some inconsistencies. Did you recently do a stock count?",
                yes_label    = "Yes, recently counted",
                no_label     = "Not recently",
                priority     = 3,
                trigger      = "signal_conflict",
            ))

        # Sort by priority and cap at MAX_ACTIVE_NUDGES
        nudges.sort(key=lambda n: n.priority)
        return nudges[:self.MAX_ACTIVE_NUDGES]


def process_nudge_response(
    product,
    nudge_trigger: str,
    response: str,
    value: Optional[float] = None,
) -> None:
    """
    Process a user's response to a nudge.
    Routes to the appropriate EventProcessor action.
    NEVER called directly from the API — always goes through EventProcessor.
    """
    from apps.inventory.events import EventProcessor
    from apps.inventory.models import InventoryEvent

    processor = EventProcessor(product)

    if nudge_trigger == "low_confidence" and value is not None:
        # User provided an approximate count → record as STOCK_COUNT
        processor.record(
            event_type        = InventoryEvent.STOCK_COUNT,
            quantity          = 0,
            verified_quantity = int(value),
            notes             = "Provided via nudge prompt",
            occurred_at       = timezone.now(),
        )

    elif nudge_trigger == "no_recent_sales" and response == "no":
        # User confirmed stockout → record estimated quantity as 0
        processor.record(
            event_type        = InventoryEvent.STOCK_COUNT,
            quantity          = 0,
            verified_quantity = 0,
            notes             = "Confirmed out of stock via nudge",
            occurred_at       = timezone.now(),
        )

    elif nudge_trigger == "stockout_suspected" and response == "no":
        # System thought stockout but user says no → bump confidence
        from django.db.models import F
        from apps.inventory.models import Product
        Product.objects.filter(pk=product.pk).update(
            confidence_score = F("confidence_score") * 1.2
        )

    logger.info(
        "Nudge response processed for %s: trigger=%s response=%s value=%s",
        product.sku, nudge_trigger, response, value,
    )