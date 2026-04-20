from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.inventory.models import Product
from apps.notifications.services.inactivity_engine import evaluate_user_inactivity
from apps.notifications.services.insight_engine import generate_product_insight
from apps.notifications.services.notification_service import notify_user


@dataclass
class RunProactiveChecksResult:
    users_processed: int = 0
    products_checked: int = 0
    notifications_created: int = 0
    duplicate_notifications: int = 0
    inactivity_notifications: int = 0


def run_proactive_checks(
    *,
    user_limit: int | None = None,
    max_products_per_user: int | None = None,
    dry_run: bool = False,
) -> RunProactiveChecksResult:
    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by("date_joined")
    result = RunProactiveChecksResult()

    for index, user in enumerate(users.iterator(), start=1):
        if user_limit and index > user_limit:
            break

        result.users_processed += 1
        products = Product.objects.filter(owner=user, is_active=True).order_by("name")

        for product_index, product in enumerate(products.iterator(), start=1):
            if max_products_per_user and product_index > max_products_per_user:
                break

            result.products_checked += 1
            insight = generate_product_insight(product)
            if not insight.should_notify:
                continue

            if dry_run:
                result.notifications_created += 1
                continue

            dispatch = notify_user(
                user,
                insight.message,
                insight.notification_type,
                insight.reference_id,
                severity=insight.severity,
                title=insight.title,
                metadata=insight.metadata,
            )
            if dispatch.created:
                result.notifications_created += 1
            else:
                result.duplicate_notifications += 1

        inactivity = evaluate_user_inactivity(user)
        if not inactivity.should_notify:
            continue

        if dry_run:
            result.inactivity_notifications += 1
            continue

        dispatch = notify_user(
            user,
            inactivity.message,
            inactivity.notification_type,
            inactivity.reference_id,
            severity=inactivity.severity,
            title="Activity check",
            metadata=inactivity.metadata,
        )
        if dispatch.created:
            result.inactivity_notifications += 1
        else:
            result.duplicate_notifications += 1

    return result


class Command(BaseCommand):
    help = "Run proactive inventory and inactivity checks."

    def add_arguments(self, parser):
        parser.add_argument("--user-limit", type=int, default=None)
        parser.add_argument("--max-products", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        result = run_proactive_checks(
            user_limit=options["user_limit"],
            max_products_per_user=options["max_products"],
            dry_run=options["dry_run"],
        )
        mode = "dry-run" if options["dry_run"] else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: users={result.users_processed}, products={result.products_checked}, "
                f"notifications={result.notifications_created}, inactivity={result.inactivity_notifications}, "
                f"duplicates={result.duplicate_notifications}"
            )
        )
