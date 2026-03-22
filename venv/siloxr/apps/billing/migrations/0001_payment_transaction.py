from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider", models.CharField(default="paystack", max_length=20)),
                ("reference", models.CharField(max_length=80, unique=True)),
                ("plan_key", models.CharField(default="pro_monthly", max_length=40)),
                ("currency", models.CharField(default="NGN", max_length=10)),
                ("amount_naira", models.DecimalField(decimal_places=2, max_digits=12)),
                ("amount_kobo", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("initialized", "Initialized"), ("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("abandoned", "Abandoned")], default="initialized", max_length=20)),
                ("authorization_url", models.URLField(blank=True, default="")),
                ("access_code", models.CharField(blank=True, default="", max_length=120)),
                ("gateway_response", models.CharField(blank=True, default="", max_length=120)),
                ("raw_initialize", models.JSONField(blank=True, default=dict)),
                ("raw_verify", models.JSONField(blank=True, default=dict)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_transactions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "billing_payment_transaction",
                "ordering": ["-created_at"],
            },
        ),
    ]
