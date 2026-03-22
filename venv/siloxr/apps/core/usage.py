from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone


@dataclass(frozen=True)
class UsagePolicy:
    tier: str
    unlimited: bool
    refresh_interval_seconds: int
    policy_summary: str


class UsagePolicyService:
    """
    Commercial access policy.

    Free users have full system access but limited refresh frequency.
    Pro users have the same system with unlimited frequency.
    """

    FREE_REFRESH_INTERVAL_SECONDS = 5 * 60

    def get_policy(self, user) -> UsagePolicy:
        if getattr(user, "is_pro", False):
            return UsagePolicy(
                tier="pro",
                unlimited=True,
                refresh_interval_seconds=0,
                policy_summary="Unlimited intelligence refreshes and interaction frequency.",
            )

        return UsagePolicy(
            tier="free",
            unlimited=False,
            refresh_interval_seconds=self.FREE_REFRESH_INTERVAL_SECONDS,
            policy_summary="Full intelligence access with a managed refresh cadence for production sustainability.",
        )

    def enforce_refresh_window(self, user, scope: str):
        """
        Returns None if access is allowed, otherwise a small throttle payload.
        """
        policy = self.get_policy(user)
        if policy.unlimited:
            return None

        cache_key = f"siloxr:usage:{user.id}:{scope}"
        now = timezone.now()
        last_seen = cache.get(cache_key)
        if last_seen is not None:
            elapsed = max(0, int((now - last_seen).total_seconds()))
            remaining = policy.refresh_interval_seconds - elapsed
            if remaining > 0:
                next_refresh_at = now + timedelta(seconds=remaining)
                return {
                    "error": "frequency_limited",
                    "detail": (
                        "Free access includes the full decision system, but live refreshes are rate-managed. "
                        f"Try again in about {remaining} seconds."
                    ),
                    "next_refresh_at": next_refresh_at.isoformat(),
                    "refresh_interval_seconds": policy.refresh_interval_seconds,
                }

        cache.set(cache_key, now, timeout=policy.refresh_interval_seconds)
        return None
