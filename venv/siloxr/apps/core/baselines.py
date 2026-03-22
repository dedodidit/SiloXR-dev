import re

from django.db.models import Avg
from django.db.utils import OperationalError

from apps.core.models import NigeriaBaselineProduct


SPAN_RE = re.compile(r"\[span_[^\]]+\]\(start_span\)|\[span_[^\]]+\]\(end_span\)")


def clean_source_text(value: str) -> str:
    return re.sub(r"\s+", " ", SPAN_RE.sub("", value or "")).strip()


def normalize_category(value: str) -> str:
    text = clean_source_text(value).lower().replace(" ", "_")
    aliases = {
        "beverage": "beverages",
        "drinks": "beverages",
        "drink": "beverages",
        "bulk-goods": "bulk_goods",
        "distributor": "distributors",
    }
    return aliases.get(text, text)


def normalize_industry(value: str) -> str:
    text = clean_source_text(value).lower().replace("&", "and").strip()
    aliases = {
        "retail": "retail",
        "supermarket": "retail",
        "mini supermarket": "retail",
        "mini-supermarket": "retail",
        "fmcg": "retail",
        "food": "retail",
        "food and beverage": "retail",
        "food beverage": "retail",
        "grocery": "retail",
        "other": "retail",
        "pharmacy": "pharmacy",
        "pharma": "pharmacy",
        "drugstore": "pharmacy",
        "chemist": "pharmacy",
        "wholesale": "wholesale",
        "distribution": "wholesale",
        "distributor": "wholesale",
        "wholesale / distribution": "wholesale",
        "hardware": "wholesale",
        "hardware and building": "wholesale",
        "hardware building": "wholesale",
        "building materials": "wholesale",
    }
    return aliases.get(text, text or "retail")


def normalize_product_name(product_name: str, category: str = "") -> str:
    name = clean_source_text(product_name).lower()
    category = normalize_category(category)

    keyword_map = {
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

    for needles, generic in keyword_map.get(category, []):
        if any(needle in name for needle in needles):
            return generic

    fallback = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return fallback or normalize_category(category) or "general_merchandise"


class NigeriaBaselineService:
    COUNTRY = "nigeria"

    def for_product(self, product):
        industry = normalize_industry(getattr(product.owner, "business_type", "") or "retail")
        category = normalize_category(getattr(product, "category", ""))
        generic = normalize_product_name(getattr(product, "name", ""), category)
        qs = NigeriaBaselineProduct.objects.filter(country=self.COUNTRY, industry=industry).defer("avg_unit_price")

        try:
            candidate = qs.filter(generic_category=generic).order_by("-avg_weekly_turnover").first() if generic else None
        except OperationalError:
            return None
        if candidate is None and category:
            try:
                aggregate = qs.filter(category=category).aggregate(
                    avg_weekly_turnover=Avg("avg_weekly_turnover"),
                    demand_std=Avg("demand_std"),
                    daily_demand=Avg("daily_demand"),
                    cv_estimate=Avg("cv_estimate"),
                    lead_time_days=Avg("lead_time_days"),
                )
            except OperationalError:
                return None
            if aggregate["avg_weekly_turnover"] is not None:
                return {
                    "source": "baseline_category",
                    "generic_category": category,
                    "avg_weekly_turnover": float(aggregate["avg_weekly_turnover"]),
                    "demand_std": float(aggregate["demand_std"] or 0.0),
                    "daily_demand": float(aggregate["daily_demand"] or 0.0),
                    "cv_estimate": float(aggregate["cv_estimate"] or 0.0),
                    "lead_time_days": int(round(float(aggregate["lead_time_days"] or 3.0))),
                    "message": "Based on similar businesses in Nigeria",
                }
        if candidate is None:
            return None
        return {
            "source": "baseline_product",
            "generic_category": candidate.generic_category,
            "avg_weekly_turnover": float(candidate.avg_weekly_turnover),
            "demand_std": float(candidate.demand_std),
            "daily_demand": float(candidate.daily_demand),
            "cv_estimate": float(candidate.cv_estimate),
            "lead_time_days": int(candidate.lead_time_days),
            "message": "Based on similar businesses in Nigeria",
        }
