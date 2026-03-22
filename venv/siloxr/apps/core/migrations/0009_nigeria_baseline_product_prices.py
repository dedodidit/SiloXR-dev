import csv
from pathlib import Path

from django.db import migrations, models


def load_baseline_prices(apps, schema_editor):
    NigeriaBaselineProduct = apps.get_model("core", "NigeriaBaselineProduct")
    csv_path = Path(__file__).resolve().parents[1] / "data" / "nigeria_baseline_prices.csv"
    if not csv_path.exists():
        return

    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            filters = {
                "country": "nigeria",
                "industry": row["industry"].strip().lower(),
                "category": row["category"].strip().lower(),
                "product_name": row["product_name"].strip(),
            }
            unit_type = row.get("unit_type", "").strip()
            if unit_type:
                filters["unit_type"] = unit_type

            updated = NigeriaBaselineProduct.objects.filter(**filters).update(
                bulk_price_naira=float(row["bulk_price_naira"]),
                avg_unit_price=float(row["unit_price_naira"]),
            )

            if updated:
                continue

            fallback_filters = {
                "country": "nigeria",
                "industry": row["industry"].strip().lower(),
                "category": row["category"].strip().lower(),
                "product_name": row["product_name"].strip(),
            }
            NigeriaBaselineProduct.objects.filter(**fallback_filters).update(
                bulk_price_naira=float(row["bulk_price_naira"]),
                avg_unit_price=float(row["unit_price_naira"]),
            )


def clear_baseline_prices(apps, schema_editor):
    NigeriaBaselineProduct = apps.get_model("core", "NigeriaBaselineProduct")
    csv_path = Path(__file__).resolve().parents[1] / "data" / "nigeria_baseline_prices.csv"
    if not csv_path.exists():
        return

    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            NigeriaBaselineProduct.objects.filter(
                country="nigeria",
                industry=row["industry"].strip().lower(),
                category=row["category"].strip().lower(),
                product_name=row["product_name"].strip(),
            ).update(
                bulk_price_naira=None,
                avg_unit_price=None,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_nigeria_baseline_product_avg_unit_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="nigeriabaselineproduct",
            name="bulk_price_naira",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.RunPython(load_baseline_prices, clear_baseline_prices),
    ]
