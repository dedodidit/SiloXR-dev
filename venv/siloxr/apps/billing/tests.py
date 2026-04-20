from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.billing.enums import FeatureFlag, PlanType
from apps.billing.models import Business, Subscription
from apps.billing.services import (
    COUNTRY_TIER_MAP,
    PRICING_TIER_A,
    PRICING_TIER_B,
    PRICING_TIER_C,
    FeatureGateService,
    PricingService,
)


class PricingServiceTests(TestCase):
    def test_country_tier_mapping_uses_explicit_coverage(self):
        self.assertEqual(COUNTRY_TIER_MAP["NG"], PRICING_TIER_A)
        self.assertEqual(COUNTRY_TIER_MAP["ZA"], PRICING_TIER_B)
        self.assertEqual(COUNTRY_TIER_MAP["US"], PRICING_TIER_C)

    def test_unknown_country_falls_back_to_tier_b_and_usd(self):
        quote = PricingService.get_price("BR", PlanType.CORE)
        self.assertEqual(quote.tier, PRICING_TIER_B)
        self.assertEqual(quote.currency, "USD")
        self.assertEqual(str(quote.amount), "20.00")

    def test_country_names_are_normalized_to_iso_codes(self):
        quote = PricingService.get_price("ghana", PlanType.PRO)
        self.assertEqual(quote.country, "GH")
        self.assertEqual(quote.currency, "GHS")
        self.assertEqual(str(quote.amount), "450.00")

    def test_enterprise_has_no_price(self):
        quote = PricingService.get_price("US", PlanType.ENTERPRISE)
        self.assertIsNone(quote.amount)
        self.assertIsNone(quote.amount_usd_reference)


class FeatureGateServiceTests(TestCase):
    def test_free_plan_is_limited_to_data_layer(self):
        self.assertTrue(FeatureGateService.has_access(PlanType.FREE, FeatureFlag.CREATE_PRODUCTS))
        self.assertTrue(FeatureGateService.has_access(PlanType.FREE, FeatureFlag.VIEW_BASIC_SIGNALS))
        self.assertFalse(FeatureGateService.has_access(PlanType.FREE, FeatureFlag.VIEW_REVENUE_GAP))
        self.assertFalse(FeatureGateService.has_access(PlanType.FREE, FeatureFlag.VIEW_FORECAST))

    def test_core_plan_unlocks_decision_layer_only(self):
        self.assertTrue(FeatureGateService.has_access(PlanType.CORE, FeatureFlag.VIEW_REVENUE_GAP))
        self.assertTrue(FeatureGateService.has_access(PlanType.CORE, FeatureFlag.VIEW_ACTIONS))
        self.assertFalse(FeatureGateService.has_access(PlanType.CORE, FeatureFlag.VIEW_FORECAST))
        self.assertFalse(FeatureGateService.has_access(PlanType.CORE, FeatureFlag.VIEW_PORTFOLIO_INSIGHTS))

    def test_pro_plan_unlocks_intelligence_layer(self):
        self.assertTrue(FeatureGateService.has_access(PlanType.PRO, FeatureFlag.VIEW_FORECAST))
        self.assertTrue(FeatureGateService.has_access(PlanType.PRO, FeatureFlag.VIEW_BUSINESS_HEALTH_REPORT))
        self.assertTrue(FeatureGateService.has_access(PlanType.PRO, FeatureFlag.VIEW_PORTFOLIO_INSIGHTS))
        self.assertFalse(FeatureGateService.has_access(PlanType.PRO, FeatureFlag.API_ACCESS))

    def test_enterprise_plan_has_unrestricted_access(self):
        self.assertTrue(FeatureGateService.has_access(PlanType.ENTERPRISE, FeatureFlag.API_ACCESS))
        self.assertTrue(FeatureGateService.has_access(PlanType.ENTERPRISE, FeatureFlag.MULTI_LOCATION))
        self.assertTrue(FeatureGateService.has_access(PlanType.ENTERPRISE, FeatureFlag.MANAGE_INTEGRATIONS))


class BusinessSubscriptionModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="biz-owner",
            email="owner@siloxr.com",
            password="Secret123!",
            tier=PlanType.FREE,
        )

    def test_business_uses_country_driven_currency(self):
        business = Business.objects.create(
            owner=self.user,
            name="Acme Retail",
            country="ng",
            currency="USD",
        )
        self.assertEqual(business.country, "NG")
        self.assertEqual(business.currency, "NGN")

    def test_active_subscription_is_exposed(self):
        business = Business.objects.create(name="Global Ops", country="US")
        inactive = Subscription.objects.create(business=business, plan=PlanType.CORE, active=False)
        active = Subscription.objects.create(business=business, plan=PlanType.PRO, active=True)
        self.assertNotEqual(inactive.id, business.active_subscription.id)
        self.assertEqual(active.id, business.active_subscription.id)

    def test_user_current_plan_prefers_active_subscription(self):
        business = Business.objects.create(owner=self.user, name="Acme Retail", country="GB")
        Subscription.objects.create(business=business, plan=PlanType.CORE, active=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_plan, PlanType.CORE)
        self.assertTrue(self.user.is_paid)
        self.assertFalse(self.user.is_pro)
