from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_nigeria_baseline_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="nigeriabaselineproduct",
            name="avg_unit_price",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
