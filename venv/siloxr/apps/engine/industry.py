class IndustryInsightService:
    """
    Small contextual insight layer based on the user's business type.
    """

    DEFAULTS = [
        "Update your stock regularly to improve decision accuracy.",
        "Low-friction stock counts help the system adapt faster.",
    ]

    CONTEXT = {
        "retail": [
            "Retail demand often spikes around weekends and payday windows.",
            "Fast-moving drinks and snacks usually need closer weekend monitoring.",
        ],
        "pharma": [
            "Pharmacy demand is usually steadier, so sudden drops can signal missing logs.",
            "Frequent stock counts matter most for essential items with stable demand.",
        ],
        "auto": [
            "Auto-parts demand is more irregular, so confidence improves with every logged sale.",
            "Irregular demand makes reorder timing more sensitive to stale counts.",
        ],
        "food": [
            "Food demand can shift quickly around weekends and waste events.",
            "Perishable items benefit from daily stock counts and tighter reorder timing.",
        ],
    }

    def get_insights(self, user, limit: int = 3) -> list[str]:
        business_type = (getattr(user, "business_type", "") or "").strip().lower()
        insights = self.CONTEXT.get(business_type, self.DEFAULTS)
        return insights[:limit]

    def get_operating_assumption(self, user) -> str:
        from apps.engine.bootstrap import BusinessTypeBaselineService

        baseline = BusinessTypeBaselineService().get(user)
        return baseline.assumptions_summary
