# backend/apps/notifications/models.py

import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    CHANNEL_IN_APP = "in_app"
    CHANNEL_EMAIL  = "email"
    CHANNEL_PUSH   = "push"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_WHATSAPP = "whatsapp"

    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, "In-app"),
        (CHANNEL_EMAIL,  "Email"),
        (CHANNEL_PUSH,   "Push"),
        (CHANNEL_TELEGRAM, "Telegram"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    decision    = models.ForeignKey(
        "inventory.DecisionLog", on_delete=models.CASCADE,
        null=True, blank=True, related_name="notifications"
    )
    channel     = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    title       = models.CharField(max_length=255)
    body        = models.TextField()
    confidence  = models.FloatField(default=0.5)
    is_read     = models.BooleanField(default=False)
    read_at     = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification"
        ordering = ["-created_at"]
        indexes  = [models.Index(fields=["user", "is_read", "created_at"])]

    def __str__(self):
        return f"{self.title} → {self.user.username}"


# backend/apps/notifications/models.py  — ADD to existing file

class NotificationThrottle(models.Model):
    """
    Per-product-per-channel throttle record.
    Prevents notification flooding — especially for WhatsApp.
    One record per user + product + channel combination.
    """
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notification_throttles"
    )
    product     = models.ForeignKey(
        "inventory.Product", on_delete=models.CASCADE, null=True, blank=True
    )
    channel     = models.CharField(max_length=20)   # whatsapp / telegram / email
    last_sent_at = models.DateTimeField()
    send_count_today = models.IntegerField(default=1)

    class Meta:
        db_table = "notification_throttle"
        unique_together = [("user", "product", "channel")]
        indexes = [models.Index(fields=["user", "channel", "last_sent_at"])]

    def is_throttled(self, cooldown_hours: int = 6, max_per_day: int = 1) -> bool:
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        # Check cooldown window
        if (now - self.last_sent_at).total_seconds() < cooldown_hours * 3600:
            return True
        # Check daily cap — reset if last_sent_at was yesterday
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


class TelegramProfile(models.Model):
    """
    Links a SiloXR user to a Telegram chat_id.
    Created when the user completes the /start flow with the bot.
    """
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user     = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="telegram_profile"
    )
    chat_id  = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=100, blank=True, default="")
    is_active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_telegram_profile"

    def __str__(self):
        return f"{self.user.username} → Telegram {self.chat_id}"
