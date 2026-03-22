# backend/apps/inventory/cold_start.py

"""
Cold Start Engine.

Handles the day-zero problem: what does the system know about a product
before any sales have been recorded?

The answer is: not much — but not nothing.

We use two complementary priors:

  1. KEYWORD PRIOR (product-level)
     Classifies the product as fast / medium / slow moving based on
     what the product name and category contain. A product called
     "Indomie Noodles" is fast-moving by any reasonable prior; a product
     called "Industrial Pump Seal" is slow.

  2. BUSINESS PRIOR (owner-level)
     BusinessTypeBaselineService maps the owner's business type to
     industry-appropriate operating parameters: target days of cover,
     coefficient of variation, verification cadence.
     A pharmacy's baseline for "expected days between counts" is different
     from a food vendor's.

These two priors are combined to seed:
  - Product.movement_class
  - Product.confidence_score     (always low — 0.15–0.30)
  - Product.data_maturity_score  (always 15 — floor value)
  - BurnRate (seed record so Forecast + Decision engines have something to read)

IMPORTANT INVARIANTS:
  - Cold start NEVER runs if any InventoryEvent already exists for the product.
    Real data always wins over priors. No exceptions.
  - Cold start NEVER overwrites last_verified_quantity.
    That field is ground truth and can only be written by STOCK_COUNT events.
  - The seeded BurnRate is flagged as low-confidence. The ForecastEngine
    will produce wide uncertainty bands from it, which is correct.
  - The assumptions_summary from BusinessTypeBaselineService is stored on the
    BurnRate.notes field so the user can see what assumptions were made.

SUPERSESSION:
  The first SALE event after product creation will trigger the LearningEngine,
  which will compute a real BurnRate and overwrite the seeded one. The seeded
  record is kept for audit purposes (it shows what the system assumed on day 0).

WIRING:
  Called from apps/inventory/signals.py on post_save of Product (created=True).
  Should not be called directly from views.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Movement classification — keyword-based, product-level prior
# ══════════════════════════════════════════════════════════════════════════════

# Products whose names or categories match these keywords are classified
# as fast-moving. These are FMCG / perishable / daily-use items.
# The list is deliberately conservative — false fast is worse than false slow
# because it produces tighter (less honest) uncertainty bands.
FAST_KEYWORDS = frozenset([
    # Beverages
    "coke", "coca cola", "pepsi", "fanta", "sprite", "water", "juice", "drink",
    "soft drink", "energy drink", "malta", "malt", "beer", "stout", "wine",
    "sachet water", "pure water", "bottle water", "zobo", "kunu",
    # Staples
    "rice", "beans", "flour", "semolina", "garri", "fufu", "semo", "yam",
    "bread", "loaf", "agege", "noodle", "indomie", "pasta", "spaghetti",
    "macaroni", "golden morn", "oat", "cereal", "cornflakes",
    # Oils and condiments
    "oil", "palm oil", "groundnut oil", "vegetable oil", "sunflower oil",
    "salt", "sugar", "seasoning", "maggi", "knorr", "thyme", "pepper",
    "tomato paste", "tomato", "onion", "garlic",
    # Dairy and proteins
    "egg", "chicken", "fish", "sardine", "tuna", "mackerel", "beef",
    "milk", "peak milk", "dano", "cowbell", "butter", "margarine",
    # Household consumables
    "soap", "detergent", "omo", "ariel", "persil", "key soap",
    "toothpaste", "close up", "macleans", "toothbrush",
    "toilet paper", "tissue", "serviette", "sanitary pad", "pampers",
    "nappy", "diaper", "baby wipes",
    # Airtime and data
    "airtime", "recharge", "recharge card", "data", "voucher",
    # Fuel and utilities
    "petrol", "diesel", "kerosene", "gas", "cooking gas",
    # Confectionery
    "sweet", "candy", "chocolate", "biscuit", "cookie", "choco",
    "snack", "chin chin", "puff puff",
    # Household items
    "matches", "candle", "lighter", "charcoal",
    # Pharmacy fast-movers
    "paracetamol", "ibuprofen", "vitamin", "supplement", "malaria",
    "antimalarial", "coartem", "disprin",
])

# Products matching these keywords are classified as slow-moving.
# These are durable goods, spare parts, machinery, and capital items.
SLOW_KEYWORDS = frozenset([
    # Machinery and equipment
    "machine", "machinery", "equipment", "generator", "compressor",
    "pump", "engine", "motor", "gearbox",
    # Building and construction
    "cement", "iron rod", "rebar", "plank", "roofing sheet", "tile",
    "door", "window", "gate", "fence", "block", "brick", "sand", "gravel",
    # Spare parts and industrial
    "spare part", "bearing", "belt", "seal", "valve", "gasket",
    "fitting", "coupling", "shaft", "gear", "sprocket",
    # Electronics and appliances
    "television", "tv", "laptop", "computer", "printer", "fridge",
    "refrigerator", "freezer", "air conditioner", "washing machine",
    "blender", "fan", "iron", "pressing iron",
    # Furniture
    "furniture", "chair", "table", "desk", "bed", "sofa", "wardrobe",
    "shelf", "cabinet", "cupboard", "mattress",
    # Tyres and automotive
    "tyre", "tire", "rim", "battery", "alternator", "starter",
    # Uniforms and fabric
    "uniform", "fabric", "material", "cloth", "shoe", "boot", "boot",
])

# Movement class constants — match Product.MOVEMENT_* choices
MOVEMENT_FAST   = "fast"
MOVEMENT_MEDIUM = "medium"
MOVEMENT_SLOW   = "slow"

# Confidence ceiling by movement class.
# Fast-moving items have slightly higher cold-start confidence because
# FMCG consumption is more regular and the prior is more reliable.
COLD_START_CONFIDENCE = {
    MOVEMENT_FAST:   0.22,
    MOVEMENT_MEDIUM: 0.18,
    MOVEMENT_SLOW:   0.15,
}

# Cold start maturity floor — always 15 regardless of movement class.
# Maturity only grows through real data — never through assumptions.
COLD_START_MATURITY = 15.0


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ColdStartResult:
    """
    Records what the cold start engine applied and why.
    Stored as a BurnRate notes field for auditability.
    """
    movement_class:          str
    burn_rate_per_day:       float
    burn_rate_std_dev:       float
    confidence_score:        float
    data_maturity_score:     float
    verification_cadence_days: int
    assumptions_summary:     str
    keyword_matched:         Optional[str]   # which keyword triggered classification
    business_prior_used:     str             # which business type drove the baseline
    was_applied:             bool            # False if real data already existed


def classify_movement(name: str, category: str = "") -> tuple[str, Optional[str]]:
    """
    Classify a product as fast / medium / slow based on name + category keywords.

    Returns (movement_class, matched_keyword).
    matched_keyword is the first keyword that triggered the classification,
    or None if no keyword matched (defaulting to medium).

    Case-insensitive. Checks word boundaries for short keywords to avoid
    false matches (e.g. "fan" should not match "FANTA").
    """
    text = f"{name} {category}".lower().strip()

    for kw in FAST_KEYWORDS:
        # Use whole-word matching for very short keywords (≤3 chars)
        # to avoid false positives like "oil" matching "toilet"
        if len(kw) <= 3:
            import re
            if re.search(rf"\b{re.escape(kw)}\b", text):
                return MOVEMENT_FAST, kw
        else:
            if kw in text:
                return MOVEMENT_FAST, kw

    for kw in SLOW_KEYWORDS:
        if kw in text:
            return MOVEMENT_SLOW, kw

    return MOVEMENT_MEDIUM, None


def apply_cold_start_defaults(product) -> ColdStartResult:
    """
    Apply cold start defaults to a new product.

    Called from apps/inventory/signals.py on post_save of Product (created=True).

    Will silently no-op and return was_applied=False if:
      - Any InventoryEvent already exists for this product
      - A BurnRate already exists for this product
    This ensures real data is never overwritten.

    Steps:
      1. Classify product movement from keywords
      2. Get business-type baseline from BusinessTypeBaselineService
      3. Derive seed burn rate using both (business prior + movement adjustment)
      4. Set Product.movement_class, confidence_score, data_maturity_score
      5. Write a seed BurnRate record (low confidence, clearly labelled)

    The seed BurnRate is what allows Forecast Engine to produce something
    useful on day zero — even if the bands are very wide.
    """
    from apps.inventory.models import BurnRate, InventoryEvent, Product as ProductModel
    from apps.engine.bootstrap import BusinessTypeBaselineService

    # ── Guard: never overwrite real data ──────────────────────────────────
    if InventoryEvent.objects.filter(product=product).exists():
        logger.debug(
            "Cold start skipped for %s — events already exist", product.sku
        )
        return ColdStartResult(
            movement_class            = getattr(product, "movement_class", MOVEMENT_MEDIUM),
            burn_rate_per_day         = 0.0,
            burn_rate_std_dev         = 0.0,
            confidence_score          = getattr(product, "confidence_score", 0.0),
            data_maturity_score       = getattr(product, "data_maturity_score", 0.0),
            verification_cadence_days = 1,
            assumptions_summary       = "Cold start skipped — real data exists.",
            keyword_matched           = None,
            business_prior_used       = "",
            was_applied               = False,
        )

    # ── Step 1: classify movement from keywords ───────────────────────────
    movement, matched_keyword = classify_movement(
        getattr(product, "name", ""),
        getattr(product, "category", "") or "",
    )

    # ── Step 2: get business-type baseline ────────────────────────────────
    service  = BusinessTypeBaselineService()
    baseline = service.get(product.owner)
    seed     = service.derive_seed_burn(product)

    # ── Step 3: adjust burn rate for movement class ───────────────────────
    # The business prior gives us the right order of magnitude.
    # The movement class adjusts it within that range:
    #   fast   → burn rate at the upper end of the prior range
    #   medium → burn rate as derived (no adjustment)
    #   slow   → burn rate at the lower end of the prior range
    #
    # These multipliers are conservative — we prefer to underestimate
    # burn rate on day zero to avoid producing false-urgent decisions.
    movement_multiplier = {
        MOVEMENT_FAST:   1.20,
        MOVEMENT_MEDIUM: 1.00,
        MOVEMENT_SLOW:   0.55,
    }[movement]

    adjusted_burn = max(0.05, seed["burn_rate_per_day"] * movement_multiplier)

    # Std dev scales proportionally — maintains the CV from the baseline
    adjusted_std = max(0.05, seed["burn_rate_std_dev"] * movement_multiplier)

    # Confidence uses the movement-class ceiling, never exceeding the baseline
    confidence = min(
        COLD_START_CONFIDENCE[movement],
        seed["confidence_score"],
    )

    # ── Step 4: update Product fields ─────────────────────────────────────
    ProductModel.objects.filter(pk=product.pk).update(
        movement_class      = movement,
        confidence_score    = confidence,
        data_maturity_score = COLD_START_MATURITY,
    )

    # Refresh the in-memory instance so downstream code sees the update
    product.movement_class      = movement
    product.confidence_score    = confidence
    product.data_maturity_score = COLD_START_MATURITY

    # ── Step 5: write seed BurnRate only if none exists ───────────────────
    if BurnRate.objects.filter(product=product).exists():
        logger.debug(
            "Cold start: BurnRate already exists for %s — skipping seed write",
            product.sku,
        )
        existing_br = BurnRate.objects.filter(product=product).order_by("-computed_at").first()
        return ColdStartResult(
            movement_class            = movement,
            burn_rate_per_day         = existing_br.burn_rate_per_day,
            burn_rate_std_dev         = existing_br.burn_rate_std_dev,
            confidence_score          = confidence,
            data_maturity_score       = COLD_START_MATURITY,
            verification_cadence_days = seed["verification_cadence_days"],
            assumptions_summary       = seed["assumptions_summary"],
            keyword_matched           = matched_keyword,
            business_prior_used       = baseline.business_type,
            was_applied               = False,
        )

    notes = _build_notes(
        movement          = movement,
        matched_keyword   = matched_keyword,
        business_prior    = baseline.business_type,
        adjusted_burn     = adjusted_burn,
        assumptions       = seed["assumptions_summary"],
        cadence           = seed["verification_cadence_days"],
    )

    BurnRate.objects.create(
        product              = product,
        burn_rate_per_day    = round(adjusted_burn, 4),
        burn_rate_std_dev    = round(adjusted_std, 4),
        confidence_score     = round(confidence, 4),
        sample_days          = 0,
        sample_event_count   = 0,
        window_days          = 30,
        notes                = notes,
    )

    result = ColdStartResult(
        movement_class            = movement,
        burn_rate_per_day         = round(adjusted_burn, 4),
        burn_rate_std_dev         = round(adjusted_std, 4),
        confidence_score          = round(confidence, 4),
        data_maturity_score       = COLD_START_MATURITY,
        verification_cadence_days = seed["verification_cadence_days"],
        assumptions_summary       = seed["assumptions_summary"],
        keyword_matched           = matched_keyword,
        business_prior_used       = baseline.business_type,
        was_applied               = True,
    )

    logger.info(
        "Cold start applied for %s: movement=%s, burn=%.3f/day, conf=%.2f "
        "(keyword=%r, business=%s)",
        product.sku,
        movement,
        adjusted_burn,
        confidence,
        matched_keyword,
        baseline.business_type,
    )

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Signal wiring helper — called from apps/inventory/apps.py
# ══════════════════════════════════════════════════════════════════════════════

def register_cold_start_signal() -> None:
    """
    Connect the cold_start_on_product_create handler to Product.post_save.

    Called once from InventoryConfig.ready() in apps/inventory/apps.py:

        from apps.inventory.cold_start import register_cold_start_signal
        register_cold_start_signal()

    Separated into its own function so it can be called explicitly and
    won't be accidentally connected twice if apps.py is imported more
    than once.
    """
    from django.db.models.signals import post_save
    from apps.inventory.models import Product
    post_save.connect(
        _cold_start_on_product_create,
        sender    = Product,
        dispatch_uid = "siloxr_cold_start_on_product_create",
        # dispatch_uid ensures the handler is only connected once
        # even if register_cold_start_signal() is called multiple times.
    )


def _cold_start_on_product_create(
    sender, instance, created: bool, **kwargs
) -> None:
    """
    post_save handler. Fires only on creation.
    Wraps apply_cold_start_defaults() in a try/except so a cold-start
    failure never blocks the product creation itself.
    """
    if not created:
        return
    try:
        apply_cold_start_defaults(instance)
    except Exception as exc:
        logger.error(
            "Cold start failed for product %s (%s): %s",
            getattr(instance, "sku", "unknown"),
            getattr(instance, "id", "unknown"),
            exc,
            exc_info=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _build_notes(
    movement:        str,
    matched_keyword: Optional[str],
    business_prior:  str,
    adjusted_burn:   float,
    assumptions:     str,
    cadence:         int,
) -> str:
    """
    Build a human-readable notes string for the seeded BurnRate record.
    This surfaces in the Django admin and in the FeedbackEngine audit trail.
    """
    keyword_note = (
        f"Classified as {movement}-moving based on keyword '{matched_keyword}'."
        if matched_keyword
        else f"No keyword match found — defaulting to {movement}-moving."
    )
    return (
        f"[COLD START SEED] {keyword_note} "
        f"Business prior: {business_prior or 'general'}. "
        f"Derived burn rate: {adjusted_burn:.3f} units/day. "
        f"Suggested verification cadence: every {cadence} day(s). "
        f"Assumptions: {assumptions} "
        f"This record will be superseded by the first LearningEngine run."
    )


def get_cold_start_explanation(product) -> str:
    """
    Returns a user-facing explanation of what the system is currently
    assuming about a product that has not yet accumulated real data.

    Used by the onboarding done-state and the DataQualityDetector to
    show users why confidence is low and what they can do about it.

    Example output:
      "SiloXR is currently using industry estimates for this product.
       For a retail business, we assume fast-moving items like this
       sell around 8 units per day on average. Your first stock count
       will replace these estimates with real numbers."
    """
    from apps.engine.bootstrap import BusinessTypeBaselineService
    from apps.inventory.models import BurnRate

    burn = (
        BurnRate.objects
        .filter(product=product, sample_event_count=0)
        .order_by("-computed_at")
        .first()
    )

    if burn is None or burn.sample_event_count > 0:
        # Real data exists — no explanation needed
        return ""

    service  = BusinessTypeBaselineService()
    baseline = service.get(product.owner)

    movement = getattr(product, "movement_class", MOVEMENT_MEDIUM)
    movement_label = {
        MOVEMENT_FAST:   "fast-moving",
        MOVEMENT_MEDIUM: "moderately moving",
        MOVEMENT_SLOW:   "slow-moving",
    }.get(movement, "moderately moving")

    business_label = baseline.business_type.replace("_", " ").title() or "your business type"

    return (
        f"SiloXR is currently using industry estimates for {product.name}. "
        f"For a {business_label} business, we assume {movement_label} products "
        f"like this sell approximately {burn.burn_rate_per_day:.1f} {product.unit} per day. "
        f"Your first stock count will replace these estimates with your actual numbers "
        f"and confidence will start to improve from there."
    )


def get_first_count_nudge(product) -> Optional[str]:
    """
    Returns a targeted nudge message for products still on cold-start defaults.
    Returns None if the product already has real data.

    Used by the NudgeEngine to generate the highest-priority nudge for
    new products — getting a stock count is the single highest-leverage
    action a user can take on day zero.
    """
    from apps.inventory.models import BurnRate

    burn = (
        BurnRate.objects
        .filter(product=product)
        .order_by("-computed_at")
        .first()
    )

    if burn is None:
        return (
            f"Add an opening stock count for {product.name} to get started. "
            f"It takes 10 seconds and unlocks your first real forecast."
        )

    if burn.sample_event_count == 0:
        cadence = int(burn.notes.split("every ")[1].split(" day")[0]) if "every " in (burn.notes or "") else 2
        return (
            f"{product.name} is currently running on industry estimates. "
            f"A quick stock count will give us your real numbers. "
            f"We suggest counting every {cadence} day(s) for best results."
        )

    return None