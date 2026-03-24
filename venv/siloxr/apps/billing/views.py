import json
import uuid
from datetime import timedelta
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .enums import PlanType
from .models import PaymentTransaction
from .services import PricingService


def _paystack_request(path: str, payload: dict | None = None) -> dict:
    if not settings.PAYSTACK_SECRET_KEY:
        raise RuntimeError("Paystack is not configured.")

    body = None
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(
        f"https://api.paystack.co/{path.lstrip('/')}",
        data=body,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(detail or "Paystack request failed.") from exc
    except URLError as exc:
        raise RuntimeError("Unable to reach Paystack.") from exc


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def billing_plan_catalog(request):
    country = getattr(getattr(request.user, "business_profile", None), "country", "") or getattr(request.user, "country", "")
    plans = []
    for plan in (PlanType.FREE, PlanType.CORE, PlanType.PRO, PlanType.ENTERPRISE):
        quote = PricingService.get_price(country, plan)
        plans.append(
            {
                "key": f"{plan}_monthly",
                "label": plan.title(),
                "interval": "month",
                "currency": quote.currency,
                "amount": float(quote.amount) if quote.amount is not None else None,
                "amount_usd_reference": float(quote.amount_usd_reference) if quote.amount_usd_reference is not None else None,
                "pricing_tier": quote.tier,
                "contact_sales": plan == PlanType.ENTERPRISE,
            }
        )
    return Response(
        {
            "country": PricingService.normalize_country(country),
            "currency": PricingService.get_currency(country),
            "plans": plans,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initialize_paystack_payment(request):
    plan = str(request.data.get("plan", "pro_monthly")).strip().lower()
    plan_map = {
        "core_monthly": PlanType.CORE,
        "pro_monthly": PlanType.PRO,
    }
    selected_plan = plan_map.get(plan)
    if selected_plan is None:
        return Response({"detail": "Unsupported billing plan."}, status=status.HTTP_400_BAD_REQUEST)

    country = getattr(getattr(request.user, "business_profile", None), "country", "") or getattr(request.user, "country", "")
    quote = PricingService.get_price(country, selected_plan)
    if quote.amount is None:
        return Response({"detail": "This plan is handled through contact sales."}, status=status.HTTP_400_BAD_REQUEST)

    amount_value = Decimal(str(quote.amount)).quantize(Decimal("0.01"))
    amount_minor = int(amount_value * 100)
    reference = f"SILOXR-{uuid.uuid4().hex[:16].upper()}"

    payload = {
        "email": request.user.email,
        "amount": amount_minor,
        "currency": quote.currency,
        "reference": reference,
        "callback_url": settings.PAYSTACK_CALLBACK_URL,
        "metadata": {
            "user_id": str(request.user.id),
            "plan": selected_plan,
            "business_name": request.user.business_name or request.user.username,
        },
    }

    try:
        result = _paystack_request("transaction/initialize", payload)
    except RuntimeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    if not result.get("status") or not result.get("data"):
        return Response({"detail": "Unable to initialize payment."}, status=status.HTTP_502_BAD_GATEWAY)

    data = result["data"]
    PaymentTransaction.objects.update_or_create(
        reference=reference,
        defaults={
            "user": request.user,
            "provider": PaymentTransaction.PROVIDER_PAYSTACK,
            "plan_key": plan,
            "currency": quote.currency,
            "amount_naira": amount_value,
            "amount_kobo": amount_minor,
            "status": PaymentTransaction.STATUS_INITIALIZED,
            "authorization_url": data.get("authorization_url", ""),
            "access_code": data.get("access_code", ""),
            "raw_initialize": result,
        },
    )

    return Response(
        {
            "authorization_url": data.get("authorization_url"),
            "access_code": data.get("access_code"),
            "reference": reference,
            "amount": float(amount_value),
            "currency": quote.currency,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verify_paystack_payment(request):
    reference = (request.query_params.get("reference") or "").strip()
    if not reference:
        return Response({"detail": "Payment reference is required."}, status=status.HTTP_400_BAD_REQUEST)

    transaction = PaymentTransaction.objects.filter(reference=reference, user=request.user).first()
    if transaction is None:
        return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        result = _paystack_request(f"transaction/verify/{reference}")
    except RuntimeError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    data = result.get("data") or {}
    gateway_status = str(data.get("status", "")).lower()
    transaction.raw_verify = result
    transaction.gateway_response = data.get("gateway_response", "") or data.get("status", "")

    if gateway_status == "success":
        transaction.status = PaymentTransaction.STATUS_SUCCESS
        transaction.paid_at = timezone.now()

        current_anchor = request.user.tier_expires_at if request.user.is_paid and request.user.tier_expires_at else timezone.now()
        selected_plan = PlanType.PRO if transaction.plan_key == "pro_monthly" else PlanType.CORE
        request.user.tier = selected_plan
        request.user.tier_expires_at = current_anchor + timedelta(days=30)
        request.user.save(update_fields=["tier", "tier_expires_at"])

        business = getattr(request.user, "business_profile", None)
        if business is not None:
            business.subscriptions.filter(active=True).update(active=False)
            business.subscriptions.create(plan=selected_plan, active=True)
    elif gateway_status in {"abandoned", "failed"}:
        transaction.status = gateway_status
    else:
        transaction.status = PaymentTransaction.STATUS_PENDING

    transaction.save(update_fields=["raw_verify", "gateway_response", "status", "paid_at", "updated_at"])

    return Response(
        {
            "verified": transaction.status == PaymentTransaction.STATUS_SUCCESS,
            "status": transaction.status,
            "reference": transaction.reference,
            "tier": request.user.tier,
            "tier_expires_at": request.user.tier_expires_at.isoformat() if request.user.tier_expires_at else None,
            "message": (
                "Payment confirmed. Pro access is now active."
                if transaction.status == PaymentTransaction.STATUS_SUCCESS
                else "Payment is not yet confirmed."
            ),
        }
    )
