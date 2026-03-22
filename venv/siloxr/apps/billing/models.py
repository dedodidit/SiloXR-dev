from django.conf import settings
from django.db import models


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
