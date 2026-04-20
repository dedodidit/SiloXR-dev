# backend/apps/core/models.py

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

from apps.billing.enums import PlanType

class User(AbstractUser):
    """
    Extended user. Subscription tier controls engine access.
    FREE  → tracking only
    PRO   → predictions, decisions, alerts
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email_notifications_enabled = models.BooleanField(default=True)
    # backend/apps/core/models.py — ADD to User model
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    whatsapp_enabled = models.BooleanField(default=False)
    business_type = models.CharField(
        max_length=50, blank=True, default="",
        help_text="e.g. retail, wholesale, pharmacy, food, hardware"
    )
    # backend/apps/core/models.py — ADD to User model

    CHANNEL_EMAIL    = "email"
    CHANNEL_WHATSAPP = "whatsapp"

    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL,    "Email"),
        (CHANNEL_WHATSAPP, "WhatsApp"),
    ]

    preferred_channel       = models.CharField(
        max_length=20, choices=CHANNEL_CHOICES,
        default=CHANNEL_EMAIL,
        help_text="Primary notification channel for Free tier"
    )
    whatsapp_critical_only  = models.BooleanField(
        default=False,
        help_text="If True, only send WhatsApp for ALERT_CRITICAL decisions"
    )
    business_name = models.CharField(max_length=200, blank=True, default="")
    avatar_url    = models.URLField(blank=True, default="")
    country = models.CharField(max_length=40, blank=True, default="")
    currency = models.CharField(max_length=10, blank=True, default="USD")
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=40, blank=True, default="")
    TIER_FREE = PlanType.FREE
    TIER_CORE = PlanType.CORE
    TIER_PRO = PlanType.PRO
    TIER_ENTERPRISE = PlanType.ENTERPRISE
    TIER_CHOICES = PlanType.choices

    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_FREE)
    tier_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_user"

    @property
    def current_plan(self) -> str:
        from django.utils import timezone

        business = getattr(self, "business_profile", None)
        if business is not None:
            subscription = business.active_subscription
            if subscription and subscription.active:
                return subscription.plan
        if (
            self.tier in {self.TIER_CORE, self.TIER_PRO, self.TIER_ENTERPRISE}
            and self.tier_expires_at
            and self.tier_expires_at < timezone.now()
        ):
            return self.TIER_FREE
        return self.tier or self.TIER_FREE

    @property
    def is_pro(self) -> bool:
        current_plan = self.current_plan
        if current_plan not in {self.TIER_PRO, self.TIER_ENTERPRISE}:
            return False
        return True

    @property
    def is_paid(self) -> bool:
        current_plan = self.current_plan
        return current_plan in {self.TIER_CORE, self.TIER_PRO, self.TIER_ENTERPRISE}

    def __str__(self) -> str:
        return self.email
    

# backend/apps/core/models.py — ADD

import random
from datetime import timedelta

class OTPVerification(models.Model):
    """Short-lived OTP for phone/email verification."""
    PURPOSE_PHONE    = "phone"
    PURPOSE_PASSWORD = "password"
    PURPOSE_LOGIN    = "login"

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otps"
    )
    purpose    = models.CharField(max_length=20)
    code       = models.CharField(max_length=6)
    is_used    = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_otp"

    @classmethod
    def generate(cls, user, purpose: str) -> "OTPVerification":
        # Invalidate existing OTPs for this user+purpose
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        from django.utils import timezone
        return cls.objects.create(
            user       = user,
            purpose    = purpose,
            code       = f"{random.randint(100000, 999999)}",
            expires_at = timezone.now() + timedelta(minutes=10),
        )

    def verify(self, code: str) -> bool:
        from django.utils import timezone
        if self.is_used or timezone.now() > self.expires_at:
            return False
        if self.code != code:
            return False
        self.is_used = True
        self.save(update_fields=["is_used"])
        return True


class NigeriaBaselineProduct(models.Model):
    country = models.CharField(max_length=40, default="nigeria")
    industry = models.CharField(max_length=50)
    category = models.CharField(max_length=80)
    generic_category = models.CharField(max_length=120)
    product_name = models.CharField(max_length=255)
    unit_type = models.CharField(max_length=80, blank=True, default="")
    weekly_turnover_low = models.FloatField(default=0.0)
    weekly_turnover_high = models.FloatField(default=0.0)
    avg_weekly_turnover = models.FloatField(default=0.0)
    demand_std = models.FloatField(default=0.0)
    daily_demand = models.FloatField(default=0.0)
    bulk_price_naira = models.FloatField(null=True, blank=True)
    avg_unit_price = models.FloatField(null=True, blank=True)
    cv_estimate = models.FloatField(default=0.0)
    lead_time_days = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=120, default="nigerian_retail_data_generation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_nigeria_baseline_product"
        unique_together = ("country", "industry", "category", "product_name", "unit_type")
        indexes = [
            models.Index(fields=["country", "industry", "category"]),
            models.Index(fields=["generic_category"]),
        ]

    def __str__(self) -> str:
        return f"{self.country}:{self.industry}:{self.product_name}"
