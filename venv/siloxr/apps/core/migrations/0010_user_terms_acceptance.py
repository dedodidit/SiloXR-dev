from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0009_nigeria_baseline_product_prices"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="terms_accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="terms_version",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
    ]
