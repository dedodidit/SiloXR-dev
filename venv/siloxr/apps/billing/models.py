from django.conf import settings
from django.db import models

from .enums import PlanType
from .services import PricingService


class Business(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_profile",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=200)
    country = models.CharField(max_length=8, default="OTHER")
    currency = models.CharField(max_length=10, default="USD")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_business"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.country = PricingService.normalize_country(self.country)
        self.currency = PricingService.get_currency(self.country)
        super().save(*args, **kwargs)

    @property
    def active_subscription(self):
        return self.subscriptions.filter(active=True).order_by("-updated_at", "-created_at").first()

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.CharField(max_length=20, choices=PlanType.choices, default=PlanType.FREE)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_subscription"
        ordering = ["-updated_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.business_id}:{self.plan}:{'active' if self.active else 'inactive'}"


class PaymentTransaction(models.Model):
    PROVIDER_PAYSTACK = "paystack"

    STATUS_INITIALIZED = "initialized"
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_ABANDONED = "abandoned"

    STATUS_CHOICES = [
        (STATUS_INITIALIZED, "Initialized"),
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_ABANDONED, "Abandoned"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    provider = models.CharField(max_length=20, default=PROVIDER_PAYSTACK)
    reference = models.CharField(max_length=80, unique=True)
    plan_key = models.CharField(max_length=40, default="pro_monthly")
    currency = models.CharField(max_length=10, default="NGN")
    amount_naira = models.DecimalField(max_digits=12, decimal_places=2)
    amount_kobo = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INITIALIZED)
    authorization_url = models.URLField(blank=True, default="")
    access_code = models.CharField(max_length=120, blank=True, default="")
    gateway_response = models.CharField(max_length=120, blank=True, default="")
    raw_initialize = models.JSONField(default=dict, blank=True)
    raw_verify = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "billing_payment_transaction"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.reference} ({self.status})"
