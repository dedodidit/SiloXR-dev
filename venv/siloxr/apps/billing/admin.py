from django.contrib import admin
from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "plan_key", "amount_naira", "status", "created_at")
    search_fields = ("reference", "user__username", "user__email")
    list_filter = ("provider", "status", "plan_key")
