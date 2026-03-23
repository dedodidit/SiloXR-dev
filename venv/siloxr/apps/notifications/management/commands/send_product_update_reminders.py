from django.core.management.base import BaseCommand

from apps.notifications.reminders import send_product_update_reminders


class Command(BaseCommand):
    help = "Send grouped reminder notifications for products that need a fresh stock update."

    def add_arguments(self, parser):
        parser.add_argument("--cadence-hours", type=int, default=24)
        parser.add_argument("--max-products", type=int, default=5)
        parser.add_argument("--user-limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        result = send_product_update_reminders(
            cadence_hours=options["cadence_hours"],
            max_products_per_user=options["max_products"],
            user_limit=options["user_limit"],
            dry_run=options["dry_run"],
        )
        mode = "dry-run" if options["dry_run"] else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: users={result.users_notified}, "
                f"notifications={result.notifications_created}, "
                f"stale_products={result.stale_products}"
            )
        )
