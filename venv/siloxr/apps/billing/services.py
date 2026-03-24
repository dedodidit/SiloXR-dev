from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .enums import FeatureFlag, PlanType

PRICING_TIER_A = "A"
PRICING_TIER_B = "B"
PRICING_TIER_C = "C"

COUNTRY_TIER_MAP: dict[str, str] = {
    "NG": PRICING_TIER_A,
    "GH": PRICING_TIER_A,
    "KE": PRICING_TIER_A,
    "IN": PRICING_TIER_A,
    "ZA": PRICING_TIER_B,
    "AE": PRICING_TIER_B,
    "GB": PRICING_TIER_C,
    "US": PRICING_TIER_C,
    "CA": PRICING_TIER_C,
}

COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "NG": "NGN",
    "GH": "GHS",
    "KE": "KES",
    "IN": "INR",
    "ZA": "ZAR",
    "AE": "AED",
    "GB": "GBP",
    "US": "USD",
    "CA": "CAD",
}

# Static country multipliers for localized pricing.
# These are intentional fixed commercial multipliers, not live FX rates.
CURRENCY_PRICE_MULTIPLIERS: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "NGN": Decimal("1500"),
    "GHS": Decimal("15"),
    "KES": Decimal("130"),
    "INR": Decimal("85"),
    "ZAR": Decimal("19"),
    "AED": Decimal("4"),
    "GBP": Decimal("1"),
    "CAD": Decimal("1.35"),
}

USD_REFERENCE_PRICES: dict[str, dict[str, Decimal | None]] = {
    PRICING_TIER_A: {
        PlanType.CORE: Decimal("10"),
        PlanType.PRO: Decimal("30"),
        PlanType.ENTERPRISE: None,
    },
    PRICING_TIER_B: {
        PlanType.CORE: Decimal("20"),
        PlanType.PRO: Decimal("60"),
        PlanType.ENTERPRISE: None,
    },
    PRICING_TIER_C: {
        PlanType.CORE: Decimal("40"),
        PlanType.PRO: Decimal("100"),
        PlanType.ENTERPRISE: None,
    },
}

PLAN_FEATURES: dict[str, set[FeatureFlag]] = {
    PlanType.FREE: {
        FeatureFlag.CREATE_PRODUCTS,
        FeatureFlag.RECORD_STOCK,
        FeatureFlag.RECORD_SALES,
        FeatureFlag.VIEW_BASIC_SIGNALS,
    },
    PlanType.CORE: {
        FeatureFlag.CREATE_PRODUCTS,
        FeatureFlag.RECORD_STOCK,
        FeatureFlag.RECORD_SALES,
        FeatureFlag.VIEW_BASIC_SIGNALS,
        FeatureFlag.VIEW_REVENUE_GAP,
        FeatureFlag.VIEW_PRODUCT_DEMAND_GAPS,
        FeatureFlag.VIEW_BASIC_PRIORITIZATION,
        FeatureFlag.VIEW_ACTIONS,
    },
    PlanType.PRO: {
        FeatureFlag.CREATE_PRODUCTS,
        FeatureFlag.RECORD_STOCK,
        FeatureFlag.RECORD_SALES,
        FeatureFlag.VIEW_BASIC_SIGNALS,
        FeatureFlag.VIEW_REVENUE_GAP,
        FeatureFlag.VIEW_PRODUCT_DEMAND_GAPS,
        FeatureFlag.VIEW_BASIC_PRIORITIZATION,
        FeatureFlag.VIEW_ACTIONS,
        FeatureFlag.VIEW_FORECAST,
        FeatureFlag.VIEW_CONFIDENCE_BANDS,
        FeatureFlag.VIEW_BUSINESS_HEALTH_REPORT,
        FeatureFlag.VIEW_PORTFOLIO_INSIGHTS,
    },
    PlanType.ENTERPRISE: set(FeatureFlag),
}

COUNTRY_NAME_TO_CODE: dict[str, str] = {
    "nigeria": "NG",
    "ghana": "GH",
    "kenya": "KE",
    "india": "IN",
    "south africa": "ZA",
    "united arab emirates": "AE",
    "uae": "AE",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "united states": "US",
    "usa": "US",
    "canada": "CA",
    "other": "OTHER",
}


@dataclass(frozen=True)
class PriceQuote:
    country: str
    tier: str
    plan: str
    currency: str
    amount: Decimal | None
    amount_usd_reference: Decimal | None


class PricingService:
    DEFAULT_TIER = PRICING_TIER_B
    DEFAULT_CURRENCY = "USD"

    @classmethod
    def normalize_country(cls, country: str | None) -> str:
        raw = (country or "").strip()
        if not raw:
            return "OTHER"
        upper = raw.upper()
        if upper in COUNTRY_TIER_MAP or upper == "OTHER":
            return upper
        return COUNTRY_NAME_TO_CODE.get(raw.lower(), upper if len(upper) == 2 else "OTHER")

    @classmethod
    def get_tier(cls, country: str | None) -> str:
        country_code = cls.normalize_country(country)
        return COUNTRY_TIER_MAP.get(country_code, cls.DEFAULT_TIER)

    @classmethod
    def get_currency(cls, country: str | None) -> str:
        country_code = cls.normalize_country(country)
        if country_code == "OTHER":
            return cls.DEFAULT_CURRENCY
        return COUNTRY_CURRENCY_MAP.get(country_code, cls.DEFAULT_CURRENCY)

    @classmethod
    def get_price(cls, country: str | None, plan: str) -> PriceQuote:
        normalized_plan = (plan or "").strip().lower() or PlanType.FREE
        country_code = cls.normalize_country(country)
        tier = cls.get_tier(country_code)
        currency = cls.get_currency(country_code)

        if normalized_plan == PlanType.FREE:
            return PriceQuote(
                country=country_code,
                tier=tier,
                plan=normalized_plan,
                currency=currency,
                amount=Decimal("0.00"),
                amount_usd_reference=Decimal("0.00"),
            )

        amount_usd = USD_REFERENCE_PRICES.get(tier, USD_REFERENCE_PRICES[cls.DEFAULT_TIER]).get(normalized_plan)
        if amount_usd is None:
            return PriceQuote(
                country=country_code,
                tier=tier,
                plan=normalized_plan,
                currency=currency,
                amount=None,
                amount_usd_reference=None,
            )

        multiplier = CURRENCY_PRICE_MULTIPLIERS.get(currency, Decimal("1"))
        amount = (amount_usd * multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return PriceQuote(
            country=country_code,
            tier=tier,
            plan=normalized_plan,
            currency=currency,
            amount=amount,
            amount_usd_reference=amount_usd,
        )


class FeatureGateService:
    @classmethod
    def normalize_plan(cls, plan: str | None) -> str:
        value = (plan or "").strip().lower()
        if value in {choice for choice, _ in PlanType.choices}:
            return value
        return PlanType.FREE

    @classmethod
    def has_access(cls, plan: str | None, feature_flag: str | FeatureFlag) -> bool:
        normalized_plan = cls.normalize_plan(plan)
        try:
            normalized_feature = FeatureFlag(feature_flag)
        except ValueError:
            return False
        return normalized_feature in PLAN_FEATURES.get(normalized_plan, PLAN_FEATURES[PlanType.FREE])
