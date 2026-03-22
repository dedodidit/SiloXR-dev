from django.urls import path

from .views import billing_plan_catalog, initialize_paystack_payment, verify_paystack_payment


urlpatterns = [
    path("plans/", billing_plan_catalog, name="billing-plan-catalog"),
    path("paystack/initialize/", initialize_paystack_payment, name="billing-paystack-initialize"),
    path("paystack/verify/", verify_paystack_payment, name="billing-paystack-verify"),
]
