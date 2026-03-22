import csv
from pathlib import Path

from django.db import migrations, models


def _normalize_product_name(product_name: str, category: str) -> str:
    name = (product_name or "").lower()
    category = (category or "").lower()
    maps = {
        "beverages": [
            (("coca-cola", "pepsi", "sprite", "7up", "mirinda", "bigi cola"), "carbonated_soft_drink"),
            (("water", "aquafina", "eva"), "bottled_water"),
            (("milo", "nutri-milk"), "fortified_beverage"),
            (("chivita",), "fruit_juice"),
            (("fearless", "supa komado", "mountain dew"), "energy_drink"),
            (("lipton",), "iced_tea"),
        ],
        "fmcg": [
            (("indomie", "spaghetti", "pasta"), "pasta_noodles"),
            (("maggi", "knorr"), "seasoning"),
            (("sunlight", "detergent"), "detergent"),
            (("bama", "mayonnaise"), "condiment"),
            (("salt",), "table_salt"),
            (("tomato", "tasty tom", "gino"), "tomato_paste"),
            (("milk",), "milk"),
            (("nivea",), "body_lotion"),
            (("colgate",), "toothpaste"),
            (("soap", "dettol"), "soap"),
            (("diaper", "molfix"), "diapers"),
        ],
        "grains": [
            (("sugar",), "sugar"),
            (("rice",), "rice"),
            (("garri",), "garri"),
            (("onion",), "onions"),
            (("yam",), "yam"),
            (("oil",), "cooking_oil"),
            (("pasta",), "pasta"),
        ],
        "bakery": [
            (("sausage roll", "beef roll"), "pastry_roll"),
            (("bread",), "bread"),
            (("biscuit",), "biscuits"),
        ],
        "otc": [
            (("paracetamol", "panadol", "ibuprofen"), "pain_relief"),
            (("gaviscon",), "antacid"),
            (("vitamin", "multivitamin"), "vitamins"),
            (("bonjela",), "oral_gel"),
            (("benylin",), "cough_syrup"),
            (("cetirizine", "zyncet"), "antihistamine"),
            (("robb",), "topical_ointment"),
        ],
        "prescription": [
            (("lonart", "amatem"), "antimalarial"),
            (("augmentin", "ciprotab"), "antibiotic"),
            (("amaryl", "metformin", "jardiance"), "diabetes_medication"),
            (("atacand", "amlodipine", "tenoric"), "hypertension_medication"),
            (("warfarin",), "anticoagulant"),
            (("allopurinol",), "gout_medication"),
            (("cholestyramine",), "lipid_management"),
            (("aciclovir",), "antiviral"),
            (("sayana",), "contraceptive"),
        ],
        "consumables": [
            (("condom",), "condoms"),
            (("strip",), "diagnostic_strips"),
            (("mask",), "face_masks"),
            (("bp monitor",), "blood_pressure_monitor"),
            (("nebulizer",), "nebulizer"),
            (("thermometer",), "thermometer"),
            (("cotton wool",), "cotton_wool"),
            (("sanitizer",), "hand_sanitizer"),
            (("syringe",), "syringe"),
            (("malaria test", "rdt"), "malaria_test"),
        ],
        "bulk_goods": [
            (("rice",), "bulk_rice"),
            (("sugar",), "bulk_sugar"),
            (("vegetable oil",), "bulk_vegetable_oil"),
            (("palm oil",), "bulk_palm_oil"),
            (("flour",), "bulk_flour"),
            (("garri",), "bulk_garri"),
            (("salt",), "bulk_salt"),
            (("cement",), "cement"),
            (("granite",), "granite"),
            (("block",), "sandcrete_block"),
            (("timber",), "timber"),
            (("millet", "guinea corn"), "grain"),
            (("fertilizer",), "fertilizer"),
            (("poultry feed",), "poultry_feed"),
            (("lpg", "cooking gas"), "cooking_gas"),
        ],
        "distributors": [
            (("coca-cola", "bigi soft drinks", "pepsi"), "soft_drink_distribution"),
            (("eva water",), "water_distribution"),
            (("peak milk", "milo"), "beverage_distribution"),
            (("sunlight",), "detergent_distribution"),
            (("soap", "dettol"), "soap_distribution"),
            (("ac", "blender"), "appliance_distribution"),
        ],
    }
    for needles, generic in maps.get(category, []):
        if any(needle in name for needle in needles):
            return generic
    return "_".join(filter(None, [category, name.replace(" ", "_")]))[:120]


def load_baseline(apps, schema_editor):
    Model = apps.get_model("core", "NigeriaBaselineProduct")
    csv_path = Path(__file__).resolve().parents[1] / "data" / "nigeria_baseline.csv"
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            low = float(row["weekly_turnover_low"])
            high = float(row["weekly_turnover_high"])
            avg = round((low + high) / 2.0, 4)
            cv = float(row["cv_estimate"])
            Model.objects.update_or_create(
                country="nigeria",
                industry=row["industry"],
                category=row["category"],
                product_name=row["product_name"],
                unit_type=row["unit_type"],
                defaults={
                    "generic_category": _normalize_product_name(row["product_name"], row["category"]),
                    "weekly_turnover_low": low,
                    "weekly_turnover_high": high,
                    "avg_weekly_turnover": avg,
                    "demand_std": round(cv * avg, 4),
                    "daily_demand": round(avg / 7.0, 4),
                    "cv_estimate": cv,
                    "lead_time_days": int(row["lead_time_days"]),
                    "source": "nigerian_retail_data_generation",
                },
            )


def unload_baseline(apps, schema_editor):
    Model = apps.get_model("core", "NigeriaBaselineProduct")
    Model.objects.filter(country="nigeria", source="nigerian_retail_data_generation").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_user_email_notifications_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="NigeriaBaselineProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("country", models.CharField(default="nigeria", max_length=40)),
                ("industry", models.CharField(max_length=50)),
                ("category", models.CharField(max_length=80)),
                ("generic_category", models.CharField(max_length=120)),
                ("product_name", models.CharField(max_length=255)),
                ("unit_type", models.CharField(blank=True, default="", max_length=80)),
                ("weekly_turnover_low", models.FloatField(default=0.0)),
                ("weekly_turnover_high", models.FloatField(default=0.0)),
                ("avg_weekly_turnover", models.FloatField(default=0.0)),
                ("demand_std", models.FloatField(default=0.0)),
                ("daily_demand", models.FloatField(default=0.0)),
                ("cv_estimate", models.FloatField(default=0.0)),
                ("lead_time_days", models.PositiveIntegerField(default=1)),
                ("source", models.CharField(default="nigerian_retail_data_generation", max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "core_nigeria_baseline_product",
                "indexes": [
                    models.Index(fields=["country", "industry", "category"], name="core_nigeri_country_a05016_idx"),
                    models.Index(fields=["generic_category"], name="core_nigeri_generic_53bc79_idx"),
                ],
                "unique_together": {("country", "industry", "category", "product_name", "unit_type")},
            },
        ),
        migrations.RunPython(load_baseline, unload_baseline),
    ]
