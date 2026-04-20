from django.db import models


class PlanType(models.TextChoices):
    FREE = "free", "Free"
    CORE = "core", "Core"
    PRO = "pro", "Pro"
    ENTERPRISE = "enterprise", "Enterprise"


class FeatureFlag(models.TextChoices):
    CREATE_PRODUCTS = "create_products", "Create products"
    RECORD_STOCK = "record_stock", "Record stock"
    RECORD_SALES = "record_sales", "Record sales"
    VIEW_BASIC_SIGNALS = "view_basic_signals", "View basic signals"
    VIEW_REVENUE_GAP = "view_revenue_gap", "View revenue gap"
    VIEW_PRODUCT_DEMAND_GAPS = "view_product_demand_gaps", "View product demand gaps"
    VIEW_BASIC_PRIORITIZATION = "view_basic_prioritization", "View basic prioritization"
    VIEW_ACTIONS = "view_actions", "View recommended actions"
    VIEW_FORECAST = "view_forecast", "View forecast"
    VIEW_CONFIDENCE_BANDS = "view_confidence_bands", "View confidence bands"
    VIEW_BUSINESS_HEALTH_REPORT = "view_business_health_report", "View business health report"
    VIEW_PORTFOLIO_INSIGHTS = "view_portfolio_insights", "View portfolio insights"
    MANAGE_INTEGRATIONS = "manage_integrations", "Manage integrations"
    MULTI_LOCATION = "multi_location", "Use multi-location"
    API_ACCESS = "api_access", "API access"
