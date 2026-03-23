from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.notifications.dispatch import dispatch_dashboard_brief
from apps.notifications.models import NotificationThrottle


OPENING_BRIEF_CHANNEL = "biz_open_brief"
CLOSING_BRIEF_CHANNEL = "biz_close_brief"


@dataclass
class BusinessBriefRunResult:
    brief_type: str
    users_processed: int = 0
    briefs_sent: int = 0
    skipped_outside_window: bool = False


def _current_business_time(now: datetime | None = None) -> datetime:
    current = now or timezone.now()
    tz = timezone.get_fixed_timezone(0)
    tz_name = getattr(settings, "BUSINESS_BRIEF_TIMEZONE", "") or ""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            tz = ZoneInfo(tz_name)
        except Exception:
            tz = timezone.get_current_timezone()
    return current.astimezone(tz)


def resolve_business_brief_type(now: datetime | None = None) -> str | None:
    current = _current_business_time(now)
    window_minutes = int(getattr(settings, "BUSINESS_BRIEF_WINDOW_MINUTES", 90) or 90)
    start_hour = int(getattr(settings, "BUSINESS_DAY_START_HOUR", 8) or 8)
    close_hour = int(getattr(settings, "BUSINESS_DAY_CLOSE_HOUR", 18) or 18)

    current_minutes = current.hour * 60 + current.minute
    opening_start = start_hour * 60
    closing_start = close_hour * 60

    if opening_start <= current_minutes < opening_start + window_minutes:
        return "opening"
    if closing_start <= current_minutes < closing_start + window_minutes:
        return "closing"
    return None


def _brief_channel(brief_type: str) -> str:
    return OPENING_BRIEF_CHANNEL if brief_type == "opening" else CLOSING_BRIEF_CHANNEL


def send_business_briefs(
    *,
    brief_type: str = "auto",
    dry_run: bool = False,
    user_limit: int | None = None,
    now: datetime | None = None,
) -> BusinessBriefRunResult:
    resolved_type = brief_type if brief_type in {"opening", "closing"} else resolve_business_brief_type(now)
    result = BusinessBriefRunResult(brief_type=resolved_type or "none")

    if resolved_type is None:
        result.skipped_outside_window = True
        return result

    from apps.api.views import DashboardViewSet

    channel = _brief_channel(resolved_type)
    dashboard_view = DashboardViewSet()
    User = get_user_model()
    users = User.objects.filter(is_active=True).order_by("date_joined")

    for index, user in enumerate(users.iterator(), start=1):
        if user_limit and index > user_limit:
            break
        result.users_processed += 1

        throttle = NotificationThrottle.objects.filter(
            user=user,
            product=None,
            channel=channel,
        ).first()
        if throttle and throttle.last_sent_at.date() == timezone.now().date():
            continue

        summary_data = dashboard_view._build_summary_data(user)
        if dry_run:
            result.briefs_sent += 1
            continue

        if dispatch_dashboard_brief(user, summary_data, resolved_type):
            NotificationThrottle.record(user, None, channel)
            result.briefs_sent += 1

    return result
