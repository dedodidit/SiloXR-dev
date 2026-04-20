from django.core.management.base import BaseCommand

from apps.notifications.business_briefs import send_business_briefs


class Command(BaseCommand):
    help = "Send start-of-business or close-of-business dashboard brief notifications."

    def add_arguments(self, parser):
        parser.add_argument("--brief", choices=["auto", "opening", "closing"], default="auto")
        parser.add_argument("--user-limit", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        result = send_business_briefs(
            brief_type=options["brief"],
            user_limit=options["user_limit"],
            dry_run=options["dry_run"],
        )

        if result.skipped_outside_window:
            self.stdout.write("outside-window: no business brief sent")
            return

        mode = "dry-run" if options["dry_run"] else "sent"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: type={result.brief_type}, "
                f"users={result.users_processed}, briefs={result.briefs_sent}"
            )
        )
