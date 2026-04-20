# backend/apps/notifications/models.py

import uuid
from django.conf import settings
from django.db import models


class Notification(models.Model):
    CHANNEL_IN_APP = "in_app"
    CHANNEL_EMAIL = "email"
    CHANNEL_PUSH = "push"
    CHANNEL_WHATSAPP = "whatsapp"

    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, "In-app"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_PUSH, "Push"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    decision = models.ForeignKey(
        "inventory.DecisionLog", on_delete=models.CASCADE,
        null=True, blank=True, related_name="notifications"
    )
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    title = models.CharField(max_length=255)
    body = models.TextField()
    confidence = models.FloatField(default=0.5)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read", "created_at"])]

    def __str__(self):
        return f"{self.title} → {self.user.username}"


class NotificationThrottle(models.Model):
    """
    Per-product-per-channel throttle record.
    Prevents notification flooding.
    One record per user + product + channel combination.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notification_throttles"
    )
    product = models.ForeignKey(
        "inventory.Product", on_delete=models.CASCADE, null=True, blank=True
    )
    channel = models.CharField(max_length=20)   # whatsapp / email
    last_sent_at = models.DateTimeField()
    send_count_today = models.IntegerField(default=1)

    class Meta:
        db_table = "notification_throttle"
        unique_together = [("user", "product", "channel")]
        indexes = [models.Index(fields=["user", "channel", "last_sent_at"])]

    def is_throttled(self, cooldown_hours: int = 6, max_per_day: int = 1) -> bool:
        from datetime import timedelta
        from django.utils import timezone

        now = timezone.now()
        if (now - self.last_sent_at).total_seconds() < cooldown_hours * 3600:
            return True
        if self.last_sent_at.date() == now.date() and self.send_count_today >= max_per_day:
            return True
        return False

    @classmethod
    def record(cls, user, product, channel: str) -> None:
        from django.utils import timezone

        now = timezone.now()
        obj, created = cls.objects.get_or_create(
            user=user, product=product, channel=channel,
            defaults={"last_sent_at": now, "send_count_today": 1},
        )
        if not created:
            if obj.last_sent_at.date() < now.date():
                obj.send_count_today = 1
            else:
                obj.send_count_today += 1
            obj.last_sent_at = now
            obj.save(update_fields=["last_sent_at", "send_count_today"])
