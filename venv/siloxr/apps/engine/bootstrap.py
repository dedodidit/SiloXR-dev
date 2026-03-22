from dataclasses import dataclass

from apps.core.baselines import normalize_industry


@dataclass(frozen=True)
class BusinessBaseline:
    business_type: str
    target_days_of_cover: float
    coefficient_of_variation: float
    base_confidence: float
    verification_cadence_days: int
    assumptions_summary: str


class BusinessTypeBaselineService:
    """
    Day-zero business priors used before enough first-party data exists.

    These are not ML outputs. They are conservative operational baselines
    derived from industry norms and then superseded as local history grows.
    """

    DEFAULT = BusinessBaseline(
        business_type="general",
        target_days_of_cover=18.0,
        coefficient_of_variation=0.55,
        base_confidence=0.24,
        verification_cadence_days=2,
        assumptions_summary="General commerce baseline with moderate demand volatility and 2-day verification cadence.",
    )

    BASELINES = {
        "retail": BusinessBaseline(
            business_type="retail",
            target_days_of_cover=12.0,
            coefficient_of_variation=0.65,
            base_confidence=0.28,
            verification_cadence_days=1,
            assumptions_summary="Retail baseline assumes faster movement, stronger weekly swings, and daily verification for fast-moving items.",
        ),
        "food": BusinessBaseline(
            business_type="food",
            target_days_of_cover=9.0,
            coefficient_of_variation=0.75,
            base_confidence=0.26,
            verification_cadence_days=1,
            assumptions_summary="Food baseline assumes shorter stock cover, higher volatility, and daily checks because perishables move quickly.",
        ),
        "pharma": BusinessBaseline(
            business_type="pharma",
            target_days_of_cover=21.0,
            coefficient_of_variation=0.35,
            base_confidence=0.3,
            verification_cadence_days=2,
            assumptions_summary="Pharmacy baseline assumes steadier demand, longer days of cover, and tighter control of essential stock.",
        ),
        "auto": BusinessBaseline(
            business_type="auto",
            target_days_of_cover=30.0,
            coefficient_of_variation=0.8,
            base_confidence=0.22,
            verification_cadence_days=3,
            assumptions_summary="Auto-parts baseline assumes slower but irregular demand with longer cover and wider uncertainty.",
        ),
        "wholesale": BusinessBaseline(
            business_type="wholesale",
            target_days_of_cover=24.0,
            coefficient_of_variation=0.5,
            base_confidence=0.25,
            verification_cadence_days=2,
            assumptions_summary="Wholesale baseline assumes larger lot movement, moderate volatility, and verification every two days.",
        ),
    }

    def get(self, user) -> BusinessBaseline:
        business_type = normalize_industry(getattr(user, "business_type", "") or "")
        if business_type == "pharmacy":
            business_type = "pharma"
        elif business_type == "retail":
            business_type = "retail"
        elif business_type == "wholesale":
            business_type = "wholesale"
        return self.BASELINES.get(business_type, self.DEFAULT)

    def derive_seed_burn(self, product) -> dict[str, float]:
        """
        Convert a business prior into an initial burn-rate estimate for a product
        when no learning history exists yet.
        """
        baseline = self.get(product.owner)
        estimated_quantity = max(float(getattr(product, "estimated_quantity", 0.0) or 0.0), 0.0)
        reorder_point = max(float(getattr(product, "reorder_point", 0.0) or 0.0), 0.0)

        anchor_stock = max(estimated_quantity, reorder_point * 1.6, 1.0)
        burn_rate = max(0.05, anchor_stock / baseline.target_days_of_cover)
        std_dev = max(0.05, burn_rate * baseline.coefficient_of_variation)

        return {
            "burn_rate_per_day": round(burn_rate, 4),
            "burn_rate_std_dev": round(std_dev, 4),
            "confidence_score": round(baseline.base_confidence, 4),
            "verification_cadence_days": baseline.verification_cadence_days,
            "assumptions_summary": baseline.assumptions_summary,
        }
