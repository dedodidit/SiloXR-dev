from __future__ import annotations

from dataclasses import dataclass

from django.core.cache import cache
from django.utils import timezone

from apps.engine.trust import DecisionConfidenceGate
from apps.inventory.models import Product
from apps.notifications.router import NotificationRouter


@dataclass
class ReminderRunResult:
    users_notified: int = 0
    notifications_created: int = 0
    stale_products: int = 0


def collect_stale_products_by_user():
    """
    Group active products by owner when they are overdue for a fresh count.
    """
    now = timezone.now()
    gate = DecisionConfidenceGate()
    grouped: dict = {}

    products = (
        Product.objects.filter(is_active=True, owner__is_active=True)
        .select_related("owner")
        .order_by("owner_id", "name")
    )

    for product in products.iterator():
        threshold_days = gate._staleness_threshold(product)
        last_verified = product.last_verified_at
        is_stale = last_verified is None or (now - last_verified).days > threshold_days
        if not is_stale:
            continue
        grouped.setdefault(product.owner, []).append(product)

    return grouped


def collect_stale_products_for_user(user):
    """
    Return stale active products for a single user.
    """
    if not getattr(user, "is_authenticated", False):
        return []

    now = timezone.now()
    gate = DecisionConfidenceGate()
    stale_products = []

    products = (
        Product.objects.filter(owner=user, is_active=True)
        .select_related("owner")
        .order_by("name")
    )

    for product in products.iterator():
        threshold_days = gate._staleness_threshold(product)
        last_verified = product.last_verified_at
        is_stale = last_verified is None or (now - last_verified).days > threshold_days
        if is_stale:
            stale_products.append(product)

    return stale_products


def send_product_update_reminders(
    *,
    cadence_hours: int = 24,
    max_products_per_user: int = 5,
    user_limit: int | None = None,
    dry_run: bool = False,
) -> ReminderRunResult:
    """
    Deliver grouped stale-product reminders through the user's preferred channel.
    Designed to be called by a scheduler command.
    """
    router = NotificationRouter()
    grouped = collect_stale_products_by_user()
    result = ReminderRunResult()

    for index, (user, products) in enumerate(grouped.items(), start=1):
        if user_limit and index > user_limit:
            break

        shortlisted = products[:max_products_per_user]
        result.stale_products += len(products)

        if dry_run:
            result.users_notified += 1
            continue

        delivery = router.route_product_update_reminder(
            user,
            shortlisted,
            cadence_hours=cadence_hours,
        )
        if delivery.any_delivered:
            result.users_notified += 1
            result.notifications_created += 1

    return result


def maybe_send_automated_product_update_reminder(
    user,
    *,
    cadence_hours: int = 24,
    max_products_per_user: int = 5,
    check_interval_minutes: int = 60,
):
    """
    Opportunistically send a reminder during normal user activity.

    This avoids any external scheduler while still automating reminder delivery.
    It debounces reminder checks in cache and relies on NotificationThrottle to
    suppress repeated sends inside the cadence window.
    """
    if not getattr(user, "is_authenticated", False):
        return None

    cache_key = f"auto_product_update_reminder_check:{user.id}"
    if cache.get(cache_key):
        return None

    cache.set(cache_key, True, timeout=max(60, check_interval_minutes * 60))

    stale_products = collect_stale_products_for_user(user)
    if not stale_products:
        return None

    shortlisted = stale_products[:max_products_per_user]
    return NotificationRouter().route_product_update_reminder(
        user,
        shortlisted,
        cadence_hours=cadence_hours,
    )
