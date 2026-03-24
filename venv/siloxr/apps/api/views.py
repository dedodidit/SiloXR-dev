# backend/apps/api/views.py
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

import logging
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet
from rest_framework.permissions import AllowAny
from apps.billing.enums import FeatureFlag
from apps.billing.services import FeatureGateService
from apps.inventory.models import (
    DecisionLog, ForecastSnapshot, InventoryEvent, Product, ReorderRecord,
)
from apps.inventory.events import EventProcessor
from .permissions import IsOwner
from .serializers import (
    BusinessHealthReportSerializer,
    BulkEventSyncSerializer,
    DashboardSummarySerializer,
    DecisionLogSerializer,
    ForecastAccuracySerializer,
    ForecastSnapshotSerializer,
    ForecastStripSerializer,
    InventoryEventCreateSerializer,
    InventoryEventSerializer,
    PortfolioSummarySerializer,
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReorderRecordSerializer,
)
from .pagination import EventCursorPagination, StandardPagePagination
from apps.core.services.demand_deficit_service import analyze_product_deficits
from apps.core.statistics import compute_cv, expected_shortage, get_distribution_params

logger = logging.getLogger(__name__)
FREE_UPLOAD_LIMIT_BYTES = 1 * 1024 * 1024


def _get_telegram_bot_username() -> str:
    """
    Return a normalized Telegram bot username from settings.

    This is intentionally defensive because misconfigured env values should
    degrade Telegram linking gracefully instead of crashing authenticated
    requests with a raw 500.
    """
    from django.conf import settings as djsettings

    raw_value = getattr(djsettings, "TELEGRAM_BOT_USERNAME", "")
    if raw_value is None:
        return ""

    bot_user = str(raw_value).strip().lstrip("@")
    return bot_user


def _maybe_send_automated_product_update_reminder(user) -> None:
    """
    Opportunistically trigger stale-product reminders during normal usage,
    without relying on an external scheduler.
    """
    try:
        from apps.notifications.reminders import maybe_send_automated_product_update_reminder

        maybe_send_automated_product_update_reminder(user)
    except Exception as exc:
        logger.warning(
            "Automated product reminder check failed for %s: %s",
            getattr(user, "id", None),
            exc,
        )


def _normalize_country(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_currency(value: str) -> str:
    return (value or "").strip().upper()


def _currency_for_country(country: str) -> str:
    from apps.billing.services import PricingService

    return PricingService.get_currency(country)


def _current_plan(user) -> str:
    return getattr(user, "current_plan", getattr(user, "tier", ""))


def _user_has_feature(user, feature_flag: FeatureFlag) -> bool:
    return FeatureGateService.has_access(_current_plan(user), feature_flag)


def _feature_denied_response(plan: str, feature_name: str, required_plan: str) -> Response:
    return Response(
        {
            "error": "plan_upgrade_required",
            "detail": f"{feature_name} is not available on your current plan.",
            "current_plan": plan,
            "required_plan": required_plan,
            "upgrade_url": "/billing/upgrade/",
        },
        status=status.HTTP_402_PAYMENT_REQUIRED,
    )


def _send_welcome_email(user, *, preferred_channel: str) -> bool:
    next_step = (
        "Telegram was selected as your preferred channel. We will open your Telegram linking step immediately after signup."
        if preferred_channel == user.CHANNEL_TELEGRAM else
        "Email updates are enabled for your account, so important SiloXR updates can reach you here."
    )
    subject = "Welcome to SiloXR"
    text_body = (
        f"Hi {user.username},\n\n"
        f"Welcome to SiloXR.\n\n"
        f"Your account has been created successfully.\n"
        f"{next_step}\n\n"
        f"If you need help, reply to {{from_email}}."
    )
    html_body = (
        f"<p>Hi {user.username},</p>"
        f"<p>Welcome to <strong>SiloXR</strong>.</p>"
        f"<p>Your account has been created successfully.</p>"
        f"<p>{next_step}</p>"
        f"<p>If you need help, reply to {{from_email}}.</p>"
    )
    return _send_account_email(
        user,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        log_context="Welcome email",
    )


def _email_delivery_ready() -> tuple[bool, str]:
    from django.conf import settings as djsettings

    backend = getattr(djsettings, "EMAIL_BACKEND", "")
    if not backend:
        return False, "Email backend is not configured."
    if backend == "django.core.mail.backends.smtp.EmailBackend":
        missing = []
        if not getattr(djsettings, "EMAIL_HOST", ""):
            missing.append("EMAIL_HOST")
        if not getattr(djsettings, "EMAIL_HOST_USER", ""):
            missing.append("EMAIL_HOST_USER")
        if not getattr(djsettings, "EMAIL_HOST_PASSWORD", ""):
            missing.append("EMAIL_HOST_PASSWORD")
        if missing:
            return False, f"Email settings are incomplete: {', '.join(missing)}."
    return True, "Email delivery is configured."


def _send_account_email(user, *, subject: str, text_body: str, html_body: str | None = None, log_context: str = "Account email") -> bool:
    from django.conf import settings as djsettings
    from django.core.mail import EmailMultiAlternatives

    if not getattr(user, "email", ""):
        logger.error("%s skipped because user has no email.", log_context)
        return False

    ready, detail = _email_delivery_ready()
    if not ready:
        logger.error("%s skipped for %s because %s", log_context, user.email, detail)
        return False

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body.format(from_email=djsettings.DEFAULT_FROM_EMAIL),
        from_email=djsettings.DEFAULT_FROM_EMAIL,
        to=[user.email],
        reply_to=[djsettings.DEFAULT_FROM_EMAIL],
    )
    if html_body:
        message.attach_alternative(html_body.format(from_email=djsettings.DEFAULT_FROM_EMAIL), "text/html")
    message.send(fail_silently=False)
    return True


def _send_login_email(user) -> bool:
    if not getattr(user, "email_notifications_enabled", False):
        return False

    logged_in_at = timezone.localtime(timezone.now()).strftime("%b %d, %Y at %I:%M %p %Z")
    subject = "SiloXR login alert"
    text_body = (
        f"Hi {user.username},\n\n"
        f"We noticed a successful login to your SiloXR account on {logged_in_at}.\n\n"
        f"If this was you, no action is needed.\n"
        f"If this was not you, reset your password immediately or reply to {{from_email}}."
    )
    html_body = (
        f"<p>Hi {user.username},</p>"
        f"<p>We noticed a successful login to your <strong>SiloXR</strong> account on {logged_in_at}.</p>"
        f"<p>If this was you, no action is needed.</p>"
        f"<p>If this was not you, reset your password immediately or reply to {{from_email}}.</p>"
    )
    return _send_account_email(
        user,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        log_context="Login email",
    )


# ── Products ───────────────────────────────────────────────────────────────────

# backend/apps/api/views.py  — update ProductViewSet

class ProductViewSet(ModelViewSet):
    """
    /api/v1/products/
    FREE tier: full CRUD + event recording.
    """
    permission_classes = [IsAuthenticated, IsOwner]
    pagination_class   = StandardPagePagination   # ← add this line

    def get_queryset(self):
        return (
            Product.objects
            .filter(owner=self.request.user, is_active=True)
            .prefetch_related("burn_rates", "events", "decisions")
            .order_by("-updated_at")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return ProductCreateSerializer
        return ProductListSerializer

    def list(self, request, *args, **kwargs):
        _maybe_send_automated_product_update_reminder(request.user)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        _maybe_send_automated_product_update_reminder(request.user)
        return super().retrieve(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_destroy(self, instance):
        # Soft delete — never hard-delete products with event history
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @action(
        detail=True,
        methods=["post"],
        url_path="events",
        permission_classes=[IsAuthenticated, IsOwner],
    )
    def record_event(self, request, pk=None):
        """
        POST /api/v1/products/{id}/events/

        Record a single inventory event for this product.
        Triggers the Learning → Forecast → Decision chain automatically.
        """
        product    = self.get_object()
        serializer = InventoryEventCreateSerializer(
            data=request.data,
            context={"product": product, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response(
            InventoryEventSerializer(event).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
    detail=True,
    methods=["get"],
    url_path="events/history",
    permission_classes=[IsAuthenticated, IsOwner],
)
    def event_history(self, request, pk=None):
        product = self.get_object()
        self.pagination_class = EventCursorPagination   # ← cursor for time-series
        events = (
            InventoryEvent.objects
            .filter(product=product)
            .order_by("-occurred_at")
        )
        page = self.paginate_queryset(events)
        if page is not None:
            return self.get_paginated_response(
                InventoryEventSerializer(page, many=True).data
            )
        return Response(InventoryEventSerializer(events, many=True).data)

# ── Events (bulk offline sync) ─────────────────────────────────────────────────

class EventSyncViewSet(ViewSet):
    """
    /api/v1/events/sync/

    Offline sync endpoint. Accepts a batch of events that were queued
    locally while the device was offline.

    Each event is processed independently:
    - Already-synced events (duplicate client_event_id) are skipped silently.
    - Failed events are reported individually.
    - The response includes per-event status so the client can clear
      successfully persisted events from its local IndexedDB queue.

    This endpoint is intentionally NOT atomic — partial success is correct
    behaviour for offline sync. We want to persist what we can.
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_sync(self, request):
        """
        POST /api/v1/events/sync/bulk/

        Body: { "events": [ {...}, {...} ] }
        Each event must include client_event_id for deduplication.
        """
        outer = BulkEventSyncSerializer(data=request.data)
        outer.is_valid(raise_exception=True)

        results   = []
        succeeded = 0
        skipped   = 0
        failed    = 0

        for event_data in outer.validated_data["events"]:
            product_id = event_data.pop("product_id", None)
            client_id  = event_data.get("client_event_id")

            try:
                product = Product.objects.get(
                    id=product_id, owner=request.user, is_active=True
                )
            except Product.DoesNotExist:
                failed += 1
                results.append({
                    "client_event_id": str(client_id),
                    "status":          "failed",
                    "reason":          "product_not_found",
                })
                continue

            serializer = InventoryEventCreateSerializer(
                data={**event_data, "is_offline_event": True},
                context={"product": product, "request": request},
            )

            if not serializer.is_valid():
                failed += 1
                results.append({
                    "client_event_id": str(client_id),
                    "status":          "failed",
                    "reason":          serializer.errors,
                })
                continue

            try:
                event = serializer.save()
                # Detect if this was a dedup (existing returned)
                import datetime
                was_new = event.created_at >= timezone.now() - datetime.timedelta(seconds=5)
                if was_new:
                    succeeded += 1
                    results.append({
                        "client_event_id": str(client_id),
                        "status":          "created",
                        "event_id":        str(event.id),
                    })
                else:
                    skipped += 1
                    results.append({
                        "client_event_id": str(client_id),
                        "status":          "duplicate",
                        "event_id":        str(event.id),
                    })
            except Exception as exc:
                logger.error(
                    "Bulk sync event failed (client_id=%s): %s", client_id, exc
                )
                failed += 1
                results.append({
                    "client_event_id": str(client_id),
                    "status":          "failed",
                    "reason":          "server_error",
                })

        return Response({
            "summary": {
                "total":     len(results),
                "succeeded": succeeded,
                "skipped":   skipped,
                "failed":    failed,
            },
            "results": results,
        }, status=status.HTTP_207_MULTI_STATUS)


# ── Decisions (PRO) ────────────────────────────────────────────────────────────

class DecisionViewSet(ReadOnlyModelViewSet):
    """
    /api/v1/decisions/

    Returns structured decision objects with reasoning and confidence scores.
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = DecisionLogSerializer

    def _ensure_action_access(self, request):
        if _user_has_feature(request.user, FeatureFlag.VIEW_ACTIONS):
            return None
        return _feature_denied_response(_current_plan(request.user), "Decision actions", "core")

    def get_queryset(self):
        qs = (
            DecisionLog.objects
            .filter(product__owner=self.request.user)
            .select_related("product")
            .order_by("-created_at")
        )
        # Filter to active only by default
        active_only = self.request.query_params.get("active", "true").lower()
        if active_only == "true":
            qs = qs.filter(
                is_acknowledged=False,
                expires_at__gt=timezone.now(),
            ).exclude(
                status__in=[DecisionLog.STATUS_ACTED, DecisionLog.STATUS_IGNORED]
            )
        # Filter by action severity
        severity = self.request.query_params.get("severity")
        if severity:
            severity_map = {
                "critical": [DecisionLog.ALERT_CRITICAL],
                "warning":  [DecisionLog.ALERT_LOW, DecisionLog.REORDER],
                "info":     [DecisionLog.CHECK_STOCK, DecisionLog.MONITOR],
                "ok":       [DecisionLog.HOLD],
            }
            actions = severity_map.get(severity, [])
            if actions:
                qs = qs.filter(action__in=actions)
        return qs

    def _track_behavior(self, request, decision, event_type, interaction_time_ms=None):
        from apps.inventory.models import UserBehaviorLog
        import datetime

        recent_updates = decision.product.events.filter(
            occurred_at__gte=timezone.now() - datetime.timedelta(days=7)
        ).count()
        frequency = round(recent_updates / 7.0, 3)

        UserBehaviorLog.objects.create(
            user=request.user,
            product=decision.product,
            decision=decision,
            event_type=event_type,
            interaction_time_ms=interaction_time_ms,
            product_update_frequency=frequency,
            metadata={
                "decision_status": decision.status,
                "action": decision.action,
            },
        )

    def list(self, request, *args, **kwargs):
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        from apps.core.services.demand_deficit_service import analyze_product_deficits
        from apps.core.services.demand_deficit_service import analyze_product_deficits
        from apps.core.services.demand_deficit_service import analyze_product_deficits
        from apps.core.services.demand_deficit_service import analyze_product_deficits
        from apps.core.usage import UsagePolicyService
        throttle = UsagePolicyService().enforce_refresh_window(request.user, "decisions")
        if throttle:
            return Response(throttle, status=status.HTTP_429_TOO_MANY_REQUESTS)

        response = super().list(request, *args, **kwargs)
        for decision in self.get_queryset()[:20]:
            if decision.status == DecisionLog.STATUS_SUGGESTED:
                decision.mark_viewed()
                self._track_behavior(request, decision, "decision_viewed")
        return response

    def retrieve(self, request, *args, **kwargs):
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        response = super().retrieve(request, *args, **kwargs)
        decision = self.get_object()
        if decision.status == DecisionLog.STATUS_SUGGESTED:
            decision.mark_viewed()
            self._track_behavior(request, decision, "decision_viewed")
        return response

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        """
        POST /api/v1/decisions/{id}/acknowledge/

        Mark a decision as acknowledged. Stops it appearing in active lists.
        Does NOT prevent a new decision from being generated on the next cycle.
        """
        decision = self.get_object()

        if decision.product.owner != request.user:
            raise PermissionDenied()

        if decision.is_acknowledged:
            return Response(
                {"detail": "Decision already acknowledged."},
                status=status.HTTP_200_OK,
            )

        decision.is_acknowledged = True
        decision.acknowledged_at = timezone.now()
        decision.save(update_fields=["is_acknowledged", "acknowledged_at"])

        return Response(
            DecisionLogSerializer(decision, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="act")
    def act(self, request, pk=None):
        """
        POST /api/v1/decisions/{id}/act/
        Mark a decision as acted on and optionally attach an outcome label.
        """
        decision = self.get_object()
        if decision.product.owner != request.user:
            raise PermissionDenied()

        outcome_label = (request.data.get("outcome_label") or "").strip()
        interaction_time_ms = request.data.get("interaction_time_ms")

        decision.mark_acted(outcome_label=outcome_label)
        self._track_behavior(request, decision, "decision_acted", interaction_time_ms)

        return Response(DecisionLogSerializer(decision, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="ignore")
    def ignore(self, request, pk=None):
        """
        POST /api/v1/decisions/{id}/ignore/
        Mark a decision as ignored so it leaves the active queue.
        """
        decision = self.get_object()
        if decision.product.owner != request.user:
            raise PermissionDenied()

        interaction_time_ms = request.data.get("interaction_time_ms")
        decision.mark_ignored()
        self._track_behavior(request, decision, "decision_ignored", interaction_time_ms)

        return Response(DecisionLogSerializer(decision, context={"request": request}).data)

    @action(detail=True, methods=["get"], url_path="simulate")
    def simulate(self, request, pk=None):
        """
        GET /api/v1/decisions/{id}/simulate/
        Lightweight what-if comparison for one existing decision.
        Computed on demand and cached briefly. No writes.
        """
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        decision = self.get_object()
        if decision.product.owner != request.user:
            raise PermissionDenied()

        cache_key = f"decision-simulation:{decision.id}:{decision.created_at.isoformat()}:{decision.status}"
        payload = cache.get(cache_key)
        if payload is None:
            stock = max(float(decision.product.estimated_quantity or 0.0), 0.0)
            mean = max(float(decision.burn_rate_at_decision or 0.0), 0.0)
            raw_std = 0.0
            if decision.forecast and decision.forecast.burn_rate:
                raw_std = max(float(decision.forecast.burn_rate.burn_rate_std_dev or 0.0), 0.0)
            cv = compute_cv(mean, raw_std)
            _, adj_std = get_distribution_params(mean, raw_std, cv)
            selling_price = float(decision.product.selling_price or 0.0)

            scenarios = []
            for delay in (0, 1, 3):
                remaining_stock = max(0.0, stock - (mean * delay))
                if delay == 0:
                    loss = 0.0
                else:
                    loss = expected_shortage(mean, max(adj_std, 1e-9), remaining_stock) * selling_price
                scenarios.append({
                    "delay": delay,
                    "loss": round(loss, 2),
                })

            payload = {
                "available": True,
                "scenarios": scenarios,
                # Preserve the inline-compare contract already used by the frontend.
                "recommended": {
                    "label": "Restock today",
                    "delay_days": 0,
                    "projected_stock": round(stock, 2),
                    "projected_stockout_date": None,
                    "estimated_revenue_loss": 0.0,
                    "confidence": float(decision.confidence_score or 0.0),
                },
                "alternatives": [
                    {
                        "label": "Wait 1 day",
                        "delay_days": 1,
                        "projected_stock": round(max(0.0, stock - mean), 2),
                        "projected_stockout_date": None,
                        "estimated_revenue_loss": scenarios[1]["loss"],
                        "confidence": float(decision.confidence_score or 0.0),
                    },
                    {
                        "label": "Do nothing",
                        "delay_days": 3,
                        "projected_stock": round(max(0.0, stock - (mean * 3)), 2),
                        "projected_stockout_date": None,
                        "estimated_revenue_loss": scenarios[2]["loss"],
                        "confidence": float(decision.confidence_score or 0.0),
                    },
                ],
            }
            cache.set(cache_key, payload, timeout=120)
        return JsonResponse(payload, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="acknowledge-all")
    def acknowledge_all(self, request):
        """
        POST /api/v1/decisions/acknowledge-all/

        Bulk acknowledge all active decisions for the current user.
        Useful for the "all clear" action in the dashboard.
        """
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        updated = DecisionLog.objects.filter(
            product__owner=request.user,
            is_acknowledged=False,
            expires_at__gt=timezone.now(),
        ).update(
            is_acknowledged=True,
            acknowledged_at=timezone.now(),
        )
        return Response({"acknowledged": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="top-priorities")
    def top_priorities(self, request):
        denied = self._ensure_action_access(request)
        if denied:
            return denied
        from apps.core.usage import UsagePolicyService
        throttle = UsagePolicyService().enforce_refresh_window(request.user, "decisions-priorities")
        if throttle:
            return Response(throttle, status=status.HTTP_429_TOO_MANY_REQUESTS)

        from apps.engine.priorities import get_top_priorities

        priorities = get_top_priorities(request.user.id, limit=3)
        serializer = DecisionLogSerializer(
            priorities,
            many=True,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class PortfolioViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        if not _user_has_feature(request.user, FeatureFlag.VIEW_PORTFOLIO_INSIGHTS):
            return _feature_denied_response(_current_plan(request.user), "Portfolio insights", "pro")
        from apps.engine.portfolio import PortfolioService

        summary = PortfolioService().summary_for_user(request.user)
        serializer = PortfolioSummarySerializer(
            {
                "total_revenue_at_risk": summary.total_revenue_at_risk,
                "products_needing_action": summary.products_needing_action,
                "top_decisions": summary.top_decisions,
                "forecast_accuracy": summary.forecast_accuracy,
                "confidence_score": summary.confidence_score,
                "overstock_capital": summary.overstock_capital,
            },
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessHealthViewSet(ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        if not _user_has_feature(request.user, FeatureFlag.VIEW_BUSINESS_HEALTH_REPORT):
            return _feature_denied_response(_current_plan(request.user), "Business Health", "pro")
        from apps.engine.business_health import BusinessHealthReportService

        report = BusinessHealthReportService().report_for_user(request.user)
        serializer = BusinessHealthReportSerializer(report, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ReorderRecordViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = ReorderRecordSerializer
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        return (
            ReorderRecord.objects
            .filter(product__owner=self.request.user)
            .select_related("product", "decision")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        decision_id = request.data.get("decision_id")
        product_id = request.data.get("product_id")
        notes = request.data.get("notes", "")

        decision = None
        product = None

        if decision_id:
            try:
                decision = DecisionLog.objects.select_related("product").get(
                    id=decision_id,
                    product__owner=request.user,
                )
                product = decision.product
            except DecisionLog.DoesNotExist:
                return Response({"detail": "Decision not found."}, status=status.HTTP_404_NOT_FOUND)

        if product is None and product_id:
            try:
                product = Product.objects.get(id=product_id, owner=request.user, is_active=True)
            except Product.DoesNotExist:
                return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        if product is None:
            return Response({"detail": "decision_id or product_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        suggested_quantity = int(
            request.data.get("suggested_quantity")
            or product.reorder_quantity
            or max(product.reorder_point, 1)
        )
        suggested_date = request.data.get("suggested_date")

        record = ReorderRecord.objects.create(
            product=product,
            decision=decision,
            suggested_quantity=max(1, suggested_quantity),
            suggested_date=suggested_date or getattr(decision, "expires_at", timezone.now()).date(),
            notes=notes,
        )

        if decision and decision.status in [DecisionLog.STATUS_SUGGESTED, DecisionLog.STATUS_VIEWED]:
            decision.mark_acted(outcome_label="reorder_created")

        serializer = self.get_serializer(record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        status_value = request.data.get("status")
        notes = request.data.get("notes")
        allowed = {
            ReorderRecord.STATUS_PENDING,
            ReorderRecord.STATUS_PLACED,
            ReorderRecord.STATUS_RECEIVED,
        }
        updated_fields = []

        if status_value in allowed:
            record.status = status_value
            updated_fields.append("status")
        if notes is not None:
            record.notes = notes
            updated_fields.append("notes")

        if updated_fields:
            updated_fields.append("updated_at")
            record.save(update_fields=updated_fields)

        return Response(self.get_serializer(record).data, status=status.HTTP_200_OK)


# ── Forecasts (PRO) ────────────────────────────────────────────────────────────

class ForecastViewSet(ReadOnlyModelViewSet):
    """
    /api/v1/forecasts/
    Returns ForecastSnapshot records and derived metrics.
    """
    permission_classes = [IsAuthenticated]
    serializer_class   = ForecastSnapshotSerializer

    def _ensure_forecast_access(self, request):
        if _user_has_feature(request.user, FeatureFlag.VIEW_FORECAST):
            return None
        return _feature_denied_response(_current_plan(request.user), "Forecasting", "pro")

    def get_queryset(self):
        if not _user_has_feature(self.request.user, FeatureFlag.VIEW_FORECAST):
            return ForecastSnapshot.objects.none()
        qs = ForecastSnapshot.objects.filter(
            product__owner=self.request.user
        ).select_related("product")

        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)

        return qs.order_by("forecast_date")

    @action(detail=False, methods=["get"], url_path="strip")
    def strip(self, request):
        """
        GET /api/v1/forecasts/strip/?product={id}&days=7

        Returns the compact forecast strip for a specific product.
        Used by the ForecastStrip component. Defaults to 7-day horizon.
        """
        denied = self._ensure_forecast_access(request)
        if denied:
            return denied
        from apps.core.usage import UsagePolicyService
        throttle = UsagePolicyService().enforce_refresh_window(request.user, "forecast-strip")
        if throttle:
            return Response(throttle, status=status.HTTP_429_TOO_MANY_REQUESTS)
        product_id = request.query_params.get("product")
        days       = int(request.query_params.get("days", 7))
        days       = min(max(days, 1), 30)

        if not product_id:
            return Response(
                {"detail": "product query parameter required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(
                id=product_id, owner=request.user, is_active=True
            )
        except Product.DoesNotExist:
            return Response(
                {"detail": "Product not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        import datetime

        today     = timezone.now().date()
        snapshots = (
            ForecastSnapshot.objects
            .filter(
                product=product,
                forecast_date__gte=today,
                forecast_date__lte=today + datetime.timedelta(days=days),
            )
            .order_by("forecast_date")
        )

        return Response(ForecastStripSerializer(snapshots, many=True).data)

    @action(detail=False, methods=["get"], url_path="accuracy")
    def accuracy(self, request):
        """
        GET /api/v1/forecasts/accuracy/?product={id}

        Returns historical accuracy metrics for a product.
        Powered by the Feedback Engine's resolved snapshots.
        """
        denied = self._ensure_forecast_access(request)
        if denied:
            return denied
        product_id = request.query_params.get("product")
        if not product_id:
            return Response(
                {"detail": "product query parameter required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(
                id=product_id, owner=request.user, is_active=True
            )
        except Product.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        resolved = list(
            ForecastSnapshot.objects
            .filter(
                product=product,
                actual_quantity__isnull=False,
            )
            .order_by("-forecast_date")[:90]
        )

        if len(resolved) < 3:
            return Response({
                "detail": "Insufficient resolved forecasts for accuracy reporting.",
                "resolved_count": len(resolved),
            }, status=status.HTTP_200_OK)

        from apps.engine.feedback import ErrorCalculator
        report = ErrorCalculator().calculate(product, resolved)
        if report is None:
            return Response(
                {"detail": "Could not compute accuracy metrics."},
                status=status.HTTP_200_OK,
            )
        import math

        total_actual = sum(e.actual for e in report.errors)
        total_abs_error = sum(e.abs_error for e in report.errors)
        wape = (total_abs_error / total_actual) * 100 if total_actual > 0 else 0.0
        rmse = math.sqrt(
            sum((e.error ** 2) for e in report.errors) / max(1, len(report.errors))
        )
        naive_diffs = [
            abs(report.errors[idx].actual - report.errors[idx - 1].actual)
            for idx in range(1, len(report.errors))
        ]
        naive_mae = (sum(naive_diffs) / len(naive_diffs)) if naive_diffs else 0.0
        mase = (report.mae / naive_mae) if naive_mae > 0 else 0.0
        bias_pct = ((sum(e.error for e in report.errors) / total_actual) * 100) if total_actual > 0 else 0.0

        resolved_with_actuals = [
            snap for snap in resolved
            if snap.actual_quantity is not None and snap.actual_quantity > 0
        ]
        covered = [
            snap for snap in resolved_with_actuals
            if snap.lower_bound <= snap.actual_quantity <= snap.upper_bound
        ]
        interval_coverage = (
            (len(covered) / len(resolved_with_actuals)) * 100
            if resolved_with_actuals else 0.0
        )
        mean_interval_width = (
            sum((snap.upper_bound - snap.lower_bound) for snap in resolved_with_actuals) / len(resolved_with_actuals)
            if resolved_with_actuals else 0.0
        )
        nominal_coverage = 68.0
        calibration_gap = nominal_coverage - interval_coverage

        payload = {
            **report.__dict__,
            "wape": round(wape, 3),
            "rmse": round(rmse, 3),
            "mase": round(mase, 3),
            "bias_pct": round(bias_pct, 3),
            "interval_coverage": round(interval_coverage, 3),
            "mean_interval_width": round(mean_interval_width, 3),
            "calibration_gap": round(calibration_gap, 3),
            "errors": [e.__dict__ for e in report.errors],
        }

        return Response(ForecastAccuracySerializer(payload).data)


# ── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardViewSet(ViewSet):
    """
    /api/v1/dashboard/

    Single-call aggregation of the full business state.
    Designed for the initial dashboard load — one HTTP request.

    FREE users get: product summary, urgent stock flags, avg confidence.
    PRO users get: all of the above + active decisions, stockout forecasts.
    """
    permission_classes = [IsAuthenticated]

    def _build_summary_data(self, user):
        from apps.core.usage import UsagePolicyService
        from apps.engine.industry import IndustryInsightService
        from apps.engine.priorities import get_top_priorities
        from apps.inventory.models import BurnRate
        can_view_actions = _user_has_feature(user, FeatureFlag.VIEW_ACTIONS)
        can_view_revenue_gap = _user_has_feature(user, FeatureFlag.VIEW_REVENUE_GAP)
        can_view_forecast = _user_has_feature(user, FeatureFlag.VIEW_FORECAST)
        can_view_portfolio = _user_has_feature(user, FeatureFlag.VIEW_PORTFOLIO_INSIGHTS)

        products = Product.objects.filter(
            owner=user, is_active=True
        ).prefetch_related("burn_rates", "decisions")

        total = products.count()
        avg_conf = (
            sum(p.confidence_score for p in products) / total
            if total > 0 else 0.0
        )
        low_conf = sum(1 for p in products if p.confidence_score < 0.4)
        urgent = [p for p in products if p.needs_verification]
        now = timezone.now()
        stale_cutoff = now - timedelta(days=2)
        stale_products = [
            p for p in products
            if not p.last_verified_at or p.last_verified_at < stale_cutoff
        ]

        active_decisions = list(
            DecisionLog.objects
            .filter(
                product__owner=user,
                is_acknowledged=False,
                expires_at__gt=now,
            )
            .exclude(status__in=[DecisionLog.STATUS_ACTED, DecisionLog.STATUS_IGNORED])
            .select_related("product")
            .order_by("-priority_score", "-created_at")[:20]
        ) if can_view_actions else []
        top_priorities = get_top_priorities(user.id, limit=3) if can_view_actions else []
        critical_count = sum(
            1 for d in active_decisions if d.action == DecisionLog.ALERT_CRITICAL
        )
        revenue_at_risk_total = round(
            sum(float(d.estimated_revenue_loss or 0.0) for d in active_decisions),
            2,
        ) if can_view_revenue_gap else 0.0
        today = now.date()
        import datetime
        stockouts_7d = (
            ForecastSnapshot.objects
            .filter(
                product__owner=user,
                forecast_date=today + datetime.timedelta(days=7),
                lower_bound__lte=0,
            )
            .values("product")
            .distinct()
            .count()
        ) if can_view_forecast else 0

        recent_decisions = DecisionLog.objects.filter(
            product__owner=user,
            created_at__gte=now - timedelta(days=14),
        )
        actioned_decisions_14d = recent_decisions.filter(
            status=DecisionLog.STATUS_ACTED
        ).count()
        ignored_decisions_14d = recent_decisions.filter(
            status=DecisionLog.STATUS_IGNORED
        ).count()

        latest_br = (
            BurnRate.objects
            .filter(product__owner=user)
            .order_by("-computed_at")
            .values_list("computed_at", flat=True)
            .first()
        )

        user_age_days = max((timezone.now().date() - user.date_joined.date()).days + 1, 1)
        if user_age_days <= 1:
            journey_hint = "Day 1: Your first prediction is live now. Keep logging stock to sharpen it."
        elif user_age_days == 2:
            journey_hint = "Day 2: We adjusted the guidance based on your recent activity."
        elif user_age_days == 3:
            journey_hint = "Day 3: Your accuracy should start improving as the system learns your rhythm."
        else:
            journey_hint = "Keep recording sales and stock counts to keep the advice sharp."

        currency = _normalize_currency(getattr(user, "currency", "") or "USD")
        if currency == "NGN":
            currency_symbol = "₦"
        elif currency == "USD":
            currency_symbol = "$"
        elif currency == "EUR":
            currency_symbol = "€"
        elif currency == "GBP":
            currency_symbol = "£"
        else:
            currency_symbol = f"{currency} "

        if revenue_at_risk_total > 0:
            managerial_headline = f"About {currency_symbol}{int(round(revenue_at_risk_total)):,} is exposed in the current decision window."
            managerial_subtext = "Focus on the highest-risk products first to protect sales before the next stockout window."
        elif critical_count > 0:
            managerial_headline = f"{critical_count} critical alert{'s' if critical_count != 1 else ''} need management attention."
            managerial_subtext = "Clear the urgent items first so the team is not spread across low-value checks."
        elif stockouts_7d > 0:
            managerial_headline = f"{stockouts_7d} product{'s' if stockouts_7d != 1 else ''} may stock out within 7 days."
            managerial_subtext = "Use the trend view to verify whether the shortfall is structural or a temporary spike."
        else:
            managerial_headline = "Operations look stable, but the next gains come from cleaner data."
            managerial_subtext = "Keep stock counts current so the forecast layer can surface stronger managerial guidance."

        managerial_signals = [
            {
                "key": "financial_exposure",
                "title": "Revenue at risk",
                "value": f"{currency_symbol}{int(round(revenue_at_risk_total)):,}" if revenue_at_risk_total > 0 else ("Unlock with Core" if not can_view_revenue_gap else "Stable"),
                "summary": (
                    f"{critical_count} critical alert{'s' if critical_count != 1 else ''} are currently exposing near-term sales."
                    if revenue_at_risk_total > 0 else
                    ("Quantified revenue exposure becomes available on the Core decision layer." if not can_view_revenue_gap else "No immediate revenue leak is visible from the current active decisions.")
                ),
                "recommendation": "Review the critical summary and clear the highest-risk products first.",
                "tone": "critical" if revenue_at_risk_total > 0 else ("warning" if not can_view_revenue_gap else "safe"),
                "target": "decisions",
            },
            {
                "key": "stockout_window",
                "title": "7-day stockout risk",
                "value": str(stockouts_7d),
                "summary": (
                    f"{stockouts_7d} product{'s are' if stockouts_7d != 1 else ' is'} projected to hit a pessimistic stockout within a week."
                    if stockouts_7d > 0 else
                    ("Forecast-driven stockout windows become available on Pro." if not can_view_forecast else "No product is currently forecast to hit a pessimistic stockout within seven days.")
                ),
                "recommendation": "Use the trend chart to confirm whether the pressure is demand-driven or a stock-count issue.",
                "tone": "warning" if stockouts_7d > 0 else ("warning" if not can_view_forecast else "safe"),
                "target": "stockouts",
            },
            {
                "key": "verification_debt",
                "title": "Verification debt",
                "value": str(len(stale_products)),
                "summary": (
                    f"{len(stale_products)} product{'s have' if len(stale_products) != 1 else ' has'} stale or missing stock verification, which weakens decision quality."
                    if stale_products else
                    "Stock verification is current across the tracked catalog."
                ),
                "recommendation": "Push quick stock counts for stale products to improve trust in the forecast layer.",
                "tone": "warning" if stale_products else "safe",
                "target": "products",
            },
            {
                "key": "follow_through",
                "title": "Decision follow-through",
                "value": (
                    f"{actioned_decisions_14d}/{actioned_decisions_14d + ignored_decisions_14d}"
                    if (actioned_decisions_14d + ignored_decisions_14d) > 0 else
                    "No signal"
                ),
                "summary": (
                    f"{actioned_decisions_14d} decisions were acted on in the last 14 days and {ignored_decisions_14d} were ignored."
                    if (actioned_decisions_14d + ignored_decisions_14d) > 0 else
                    "We do not yet have enough follow-through data to judge operational response quality."
                ),
                "recommendation": "Use the decision queue to close the loop so the system can learn what actually helped.",
                "tone": (
                    "critical" if ignored_decisions_14d > actioned_decisions_14d and ignored_decisions_14d > 0 else
                    "warning" if actioned_decisions_14d == 0 and ignored_decisions_14d == 0 else
                    "safe"
                ),
                "target": "decisions_queue",
            },
        ]

        usage_policy = UsagePolicyService().get_policy(user)
        industry_service = IndustryInsightService()
        baseline_in_use = Product.objects.filter(
            owner=user,
            is_active=True,
            burn_rates__sample_event_count__lt=7,
        ).exists()
        operating_assumption = industry_service.get_operating_assumption(user)
        if baseline_in_use and _normalize_country(getattr(user, "country", "") or "nigeria") == "nigeria":
            operating_assumption = f"Based on similar businesses in Nigeria. {operating_assumption}"
        demand_deficits = analyze_product_deficits(user) if can_view_revenue_gap else []

        return {
            "total_products": total,
            "products_needing_action": len(urgent),
            "products_low_confidence": low_conf,
            "critical_alerts": critical_count,
            "avg_confidence": round(avg_conf, 4),
            "tier": user.current_plan,
            "is_pro": user.is_pro,
            "active_decisions": active_decisions,
            "top_priorities": top_priorities,
            "urgent_products": urgent[:10],
            "contextual_insights": industry_service.get_insights(user, limit=3),
            "user_context": {
                "name": user.first_name or user.username,
                "business_name": getattr(user, "business_name", "") or user.username,
                "business_type": getattr(user, "business_type", "") or "General",
                "country": getattr(user, "country", "") or "",
                "currency": currency,
                "tier": user.current_plan,
                "is_pro": user.is_pro,
            },
            "journey_hint": journey_hint,
            "last_learning_at": latest_br,
            "stockouts_within_7d": stockouts_7d,
            "revenue_at_risk_total": revenue_at_risk_total,
            "stale_products_count": len(stale_products),
            "actioned_decisions_14d": actioned_decisions_14d,
            "ignored_decisions_14d": ignored_decisions_14d,
            "managerial_brief": {
                "headline": managerial_headline,
                "subtext": managerial_subtext,
            },
            "managerial_signals": managerial_signals,
            "usage_policy": {
                "tier": usage_policy.tier,
                "unlimited": usage_policy.unlimited,
                "refresh_interval_seconds": usage_policy.refresh_interval_seconds,
                "policy_summary": usage_policy.policy_summary,
            },
            "operating_assumption": operating_assumption,
            "baseline_in_use": baseline_in_use,
            "demand_deficits": demand_deficits if can_view_portfolio or can_view_revenue_gap else [],
        }

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """
        GET /api/v1/dashboard/summary/

        Returns the complete dashboard state.
        """
        from apps.core.usage import UsagePolicyService

        throttle = UsagePolicyService().enforce_refresh_window(request.user, "dashboard-summary")
        if throttle:
            return Response(throttle, status=status.HTTP_429_TOO_MANY_REQUESTS)

        user     = request.user
        _maybe_send_automated_product_update_reminder(user)
        data = self._build_summary_data(user)

        serializer = DashboardSummarySerializer(data, context={"request": request})
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="alerts")
    def alerts(self, request):
        """
        GET /api/v1/dashboard/alerts/

        Returns only critical and warning-level active decisions.
        Used for the notification badge count and alert panel.
        """
        alerts = (
            DecisionLog.objects
            .filter(
                product__owner=request.user,
                action__in=[
                    DecisionLog.ALERT_CRITICAL,
                    DecisionLog.ALERT_LOW,
                    DecisionLog.REORDER,
                ],
                is_acknowledged=False,
                expires_at__gt=timezone.now(),
            )
            .select_related("product")
            .order_by("-created_at")
        )

        return Response(DecisionLogSerializer(alerts, many=True, context={"request": request}).data)

    @action(detail=False, methods=["get"], url_path="health", permission_classes=[])
    def health(self, request):
        """
        GET /api/v1/dashboard/health/

        System health check — no auth required.
        Returns engine status and last run timestamps.
        Used by monitoring tools and the admin panel.
        """
        from apps.inventory.models import BurnRate
        import datetime

        now     = timezone.now()
        cutoff  = now - datetime.timedelta(hours=25)

        stale_products = (
            Product.objects
            .filter(is_active=True)
            .exclude(burn_rates__computed_at__gte=cutoff)
            .count()
        )

        return Response({
            "status":                 "ok",
            "timestamp":              now,
            "stale_products":         stale_products,
            "engine_health":          "degraded" if stale_products > 0 else "healthy",
        })
    
# backend/apps/api/views.py  — add to bottom

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications(request):
    """
    GET /api/v1/notifications/
    Returns unread in-app notifications for the current user.
    """
    from apps.notifications.models import Notification
    _maybe_send_automated_product_update_reminder(request.user)
    unread = Notification.objects.filter(
        user=request.user, is_read=False
    ).select_related("decision__product")[:50]

    data = [{
        "id":          str(n.id),
        "title":       n.title,
        "body":        n.body,
        "channel":     n.channel,
        "confidence":  n.confidence,
        "action":      n.decision.action if n.decision else None,
        "severity":    n.decision.severity if n.decision else "info",
        "product_name": n.decision.product.name if n.decision else None,
        "product_sku": n.decision.product.sku if n.decision else None,
        "created_at":  n.created_at,
        "is_read":     n.is_read,
    } for n in unread]

    return Response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notification_status(request):
    """
    GET /api/v1/notifications/status/
    Returns whether each delivery channel is actually ready for this user.
    """
    from apps.notifications.dispatch import notification_channel_status

    return Response(notification_channel_status(request.user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """
    POST /api/v1/notifications/read/
    Marks all unread notifications as read.
    """
    from apps.notifications.models import Notification
    updated = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    return Response({"marked_read": updated})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_test_email(request):
    """
    POST /api/v1/notifications/test-email/
    Send a test email to the signed-in user so delivery can be verified live.
    """
    ready, detail = _email_delivery_ready()
    if not ready:
        return Response(
            {"ready": False, "sent": False, "detail": detail},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not getattr(request.user, "email", ""):
        return Response(
            {"ready": True, "sent": False, "detail": "Your account does not have an email address yet."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sent = False
    try:
        sent = _send_account_email(
            request.user,
            subject="SiloXR test email",
            text_body=(
                f"Hi {request.user.username},\n\n"
                "This is a test email from SiloXR.\n\n"
                "If you received this message, email delivery is working for your account."
            ),
            html_body=(
                f"<p>Hi {request.user.username},</p>"
                "<p>This is a test email from <strong>SiloXR</strong>.</p>"
                "<p>If you received this message, email delivery is working for your account.</p>"
            ),
            log_context="Test email",
        )
    except Exception as exc:
        logger.error("Test email failed for %s: %s", request.user.email, exc, exc_info=True)
        return Response(
            {"ready": True, "sent": False, "detail": "The email provider rejected the test send."},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
            "ready": True,
            "sent": sent,
            "detail": "Test email sent successfully." if sent else "Test email could not be sent.",
            "recipient": request.user.email,
        }
    )

# backend/apps/api/views.py  — add to bottom

@api_view(["POST"])
@permission_classes([])   # public — no auth required
def register(request):
    """
    POST /api/v1/auth/register/
    Creates a new Free-tier user.
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError

    User = get_user_model()

    username = request.data.get("username", "").strip()
    email    = request.data.get("email",    "").strip()
    password = request.data.get("password", "")
    business_type = request.data.get("business_type", "").strip().lower()
    business_name = request.data.get("business_name", "").strip()
    phone_number = request.data.get("phone_number", "").strip()
    country = _normalize_country(request.data.get("country", ""))
    currency = _currency_for_country(country)
    email_notifications_enabled = bool(request.data.get("email_notifications_enabled", True))
    telegram_requested = bool(request.data.get("telegram_enabled", False))
    preferred_channel = (request.data.get("preferred_channel", User.CHANNEL_EMAIL) or User.CHANNEL_EMAIL).strip().lower()
    terms_accepted = bool(request.data.get("terms_accepted", False))
    terms_version = request.data.get("terms_version", "placeholder-v1").strip() or "placeholder-v1"

    if not username or not password:
        return Response(
            {"detail": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not email:
        return Response(
            {"email": ["Email is required."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not terms_accepted:
        return Response(
            {"terms_accepted": ["You must accept the terms and conditions to continue."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if preferred_channel not in {User.CHANNEL_EMAIL, User.CHANNEL_TELEGRAM}:
        preferred_channel = User.CHANNEL_EMAIL

    if User.objects.filter(username=username).exists():
        return Response(
            {"username": ["A user with that username already exists."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {"email": ["A user with that email already exists."]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(password)
    except DjangoValidationError as e:
        return Response(
            {"password": list(e.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        tier="free",
        business_type=business_type,
        business_name=business_name,
        phone_number=phone_number or None,
        country=country,
        currency=currency,
        email_notifications_enabled=email_notifications_enabled,
        telegram_enabled=False,
        preferred_channel=preferred_channel,
        terms_accepted_at=timezone.now(),
        terms_version=terms_version,
    )

    try:
        from apps.billing.enums import PlanType
        from apps.billing.models import Business, Subscription

        business = Business.objects.create(
            owner=user,
            name=business_name or username,
            country=country,
            currency=currency,
        )
        Subscription.objects.create(
            business=business,
            plan=PlanType.FREE,
            active=True,
        )
    except Exception as exc:
        logger.error("Business profile provisioning failed for %s: %s", user.username, exc, exc_info=True)

    telegram_link = ""
    telegram_bot_user = ""
    if telegram_requested or preferred_channel == User.CHANNEL_TELEGRAM:
        try:
            from apps.notifications.telegram import generate_link_token

            token = generate_link_token(user)
            telegram_bot_user = _get_telegram_bot_username() or "siloxr_bot"
            telegram_link = f"https://t.me/{telegram_bot_user}?start={token}"
        except Exception as exc:
            logger.error("Telegram signup link generation failed for %s: %s", user.username, exc, exc_info=True)

    welcome_email_sent = False
    try:
        welcome_email_sent = _send_welcome_email(user, preferred_channel=preferred_channel)
    except Exception as exc:
        logger.error("Welcome email failed for %s: %s", user.email, exc, exc_info=True)

    return Response(
        {
            "id": str(user.id),
            "username": user.username,
            "tier": user.current_plan,
            "business_type": user.business_type,
            "country": user.country,
            "currency": user.currency,
            "preferred_channel": user.preferred_channel,
            "telegram_link": telegram_link,
            "telegram_bot_user": telegram_bot_user,
            "welcome_email_sent": welcome_email_sent,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """
    POST /api/v1/auth/login/
    Accepts username or email and returns JWT tokens.
    """
    from django.contrib.auth import authenticate, get_user_model
    from rest_framework_simplejwt.tokens import RefreshToken

    User = get_user_model()

    identifier = request.data.get("identifier", "").strip()
    password = request.data.get("password", "")

    if not identifier or not password:
        return Response(
            {"detail": "Identifier and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    username = identifier
    if "@" in identifier:
        existing = User.objects.filter(email__iexact=identifier).first()
        username = existing.username if existing else identifier

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response(
            {"detail": "Invalid username, email, or password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    refresh = RefreshToken.for_user(user)
    login_email_sent = False
    try:
        login_email_sent = _send_login_email(user)
    except Exception as exc:
        logger.error("Login email failed for %s: %s", user.email, exc, exc_info=True)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "login_email_sent": login_email_sent,
        }
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """
    GET /api/v1/auth/me/
    Returns current user info including tier and notification settings.
    """
    user = request.user
    _maybe_send_automated_product_update_reminder(user)
    return Response({
        "id":                           str(user.id),
        "username":                     user.username,
        "email":                        user.email,
        "tier":                         user.current_plan,
        "is_pro":                       user.is_pro,
        "business_name":                user.business_name,
        "business_type":                user.business_type,
        "country":                      user.country,
        "currency":                     user.currency,
        "avatar_url":                   user.avatar_url,
        "phone_number":                 user.phone_number,
        "whatsapp_enabled":             False,
        "telegram_enabled":             user.telegram_enabled,
        "preferred_channel":            user.CHANNEL_EMAIL if user.preferred_channel == "whatsapp" else user.preferred_channel,
        "whatsapp_critical_only":       False,
        "email_notifications_enabled":  user.email_notifications_enabled,
    })

# backend/apps/api/views.py — append to bottom

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_data(request):
    """
    POST /api/v1/upload/
    Accepts CSV, Excel, or PDF. Imports events via EventProcessor.
    """
    from apps.inventory.upload import UploadProcessor

    file = request.FILES.get("file")
    if not file:
        return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
    if not request.user.is_pro and int(getattr(file, "size", 0) or 0) > FREE_UPLOAD_LIMIT_BYTES:
        return Response(
            {"detail": "Free plan uploads are limited to 1MB. Upgrade to Pro for unlimited upload size."},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    ext          = file.name.rsplit(".", 1)[-1].lower()
    content      = file.read()
    default_type = request.data.get("default_event_type", "SALE")

    try:
        processor = UploadProcessor()
        result    = processor.process(content, ext, request.user, default_type)
    except ImportError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.error("Upload failed: %s", exc, exc_info=True)
        return Response({"detail": "Upload failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(result, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def upload_sample(request):
    """
    GET /api/v1/upload/sample/
    Returns a sample CSV file for download.
    """
    from apps.inventory.upload import SAMPLE_CSV, SAMPLE_SALES_CSV, SAMPLE_STOCK_CSV
    from django.http import HttpResponse
    kind = str(request.query_params.get("kind", "all")).lower()

    if kind == "sales":
        sample = SAMPLE_SALES_CSV
        filename = "siloxr_sales_sample.csv"
    elif kind == "stock":
        sample = SAMPLE_STOCK_CSV
        filename = "siloxr_stock_sample.csv"
    else:
        sample = SAMPLE_CSV
        filename = "siloxr_sample_data.csv"

    resp = HttpResponse(sample, content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def respond_to_nudge(request):
    """
    POST /api/v1/nudge/respond/
    Process a user's response to a nudge prompt.
    """
    from apps.inventory.models import Product
    from apps.engine.nudge import process_nudge_response

    product_id = request.data.get("product_id")
    trigger    = request.data.get("trigger")
    response   = request.data.get("response")
    value      = request.data.get("value")

    try:
        product = Product.objects.get(id=product_id, owner=request.user)
    except Product.DoesNotExist:
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        process_nudge_response(
            product, trigger, response,
            float(value) if value is not None else None,
        )
    except Exception as exc:
        logger.error("Nudge response failed: %s", exc)
        return Response({"detail": "Could not process response."}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"status": "processed"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_nudges(request):
    """
    GET /api/v1/nudge/
    Returns active nudge prompts for the current user's products.
    """
    from apps.inventory.models import Product
    from apps.engine.nudge import NudgeEngine

    engine  = NudgeEngine()
    nudges  = []
    products = Product.objects.filter(
        owner=request.user, is_active=True
    ).order_by("confidence_score")[:10]

    for product in products:
        for n in engine.generate(product):
            nudges.append({
                "product_id":   n.product_id,
                "product_name": n.product_name,
                "nudge_type":   n.nudge_type,
                "question":     n.question,
                "yes_label":    n.yes_label,
                "no_label":     n.no_label,
                "range_min":    n.range_min,
                "range_max":    n.range_max,
                "range_unit":   n.range_unit,
                "trigger":      n.trigger,
                "priority":     n.priority,
            })

    nudges.sort(key=lambda n: n["priority"])
    return Response(nudges[:5])   # max 5 at a time


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def coverage_status(request):
    """
    GET /api/v1/coverage/
    Returns how many products the user is monitoring vs total.
    Used by the "Monitoring X of N products" UI.
    """
    from apps.inventory.models import Product
    from apps.engine.gating import IntelligenceGate, apply_coverage_limit

    all_products = list(Product.objects.filter(owner=request.user, is_active=True))
    gate         = IntelligenceGate()
    visible, total = apply_coverage_limit(all_products, request.user, gate)

    return Response({
        "visible":      len(visible),
        "total":        total,
        "is_limited":   False,
        "upgrade_cta":  False,
    })

    # backend/apps/api/views.py — ADD

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit_insight_feedback(request):
    """
    POST /api/v1/insights/feedback/
    {
        "decision_id": "uuid",     optional
        "detector":    "StockRiskDetector",
        "product_id":  "uuid",
        "was_helpful":  true | false,
        "was_accurate": true | false,
        "comment":     ""
    }
    """
    from apps.inventory.models import InsightFeedback, Product
    from apps.inventory.models import DecisionLog

    product_id  = request.data.get("product_id")
    decision_id = request.data.get("decision_id")
    was_helpful  = request.data.get("was_helpful")
    was_accurate = request.data.get("was_accurate")

    product  = None
    decision = None

    if product_id:
        try: product = Product.objects.get(id=product_id, owner=request.user)
        except Product.DoesNotExist: pass

    if decision_id:
        try: decision = DecisionLog.objects.get(id=decision_id, product__owner=request.user)
        except DecisionLog.DoesNotExist: pass

    InsightFeedback.objects.create(
        user         = request.user,
        product      = product,
        decision     = decision,
        detector     = request.data.get("detector", ""),
        was_helpful  = was_helpful,
        was_accurate = was_accurate,
        comment      = request.data.get("comment", ""),
    )

    return Response({"status": "recorded"}, status=status.HTTP_201_CREATED)


# backend/apps/api/views.py
# REPLACE get_insights view

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_insights(request):
    """
    GET /api/v1/insights/
    Returns structured insights with prediction + impact fields.
    Pro users receive full detail. Free users receive approximated detail.
    """
    from apps.core.usage import UsagePolicyService
    throttle = UsagePolicyService().enforce_refresh_window(request.user, "insights")
    if throttle:
        return Response(throttle, status=status.HTTP_429_TOO_MANY_REQUESTS)

    from apps.engine.insights import InsightEngine
    from apps.engine.gating import IntelligenceGate

    engine   = InsightEngine()
    insights = engine.run_for_user(request.user)
    gate     = IntelligenceGate()
    can_view_revenue_gap = _user_has_feature(request.user, FeatureFlag.VIEW_REVENUE_GAP)
    can_view_actions = _user_has_feature(request.user, FeatureFlag.VIEW_ACTIONS)

    data = []
    for i in insights:
        ctx     = gate.build_context(request.user, _get_product(i.product_id))
        depth   = ctx.reasoning_depth

        prediction = i.prediction
        impact     = i.impact
        date_sig   = i.date_signal

        data.append({
            "detector":       i.detector,
            "product_id":     i.product_id,
            "product_sku":    i.product_sku,
            "product_name":   i.product_name,
            "observation":    i.observation,
            "prediction":     prediction if can_view_actions else "Monitor this product closely.",
            "recommendation": i.recommendation if can_view_actions else "Record more stock and sales activity to unlock a recommended action.",
            "impact":         impact if can_view_revenue_gap else "",
            "context":        gate.abstract_reasoning(i.context, depth),
            "reasoning":      gate.abstract_reasoning(i.reasoning, depth),
            "confidence":     i.confidence,
            "date_signal":    date_sig,
            "severity":       i.severity,
            "action_type":    i.action_type,
            "urgency_tier":   i.urgency_tier,
            "lost_sales_est": i.lost_sales_est if can_view_revenue_gap else 0,
            "is_pro_detail":  _user_has_feature(request.user, FeatureFlag.VIEW_FORECAST),
        })

    return Response(data)


# backend/apps/api/views.py
# REPLACE get_dominant_insight() with version that uses priorities.py

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_dominant_insight(request):
    """
    GET /api/v1/insights/dominant/
    Returns the single most urgent item for the hero card.

    Source selection:
      - Pro users: top active DecisionLog by priority_score
        (uses the actuarially-correct ImpactEstimator output)
      - Free users: top InsightEngine result with approximated language
        (they get real intelligence, not precise impact numbers)
    """
    from apps.engine.priorities import get_top_priorities
    from apps.engine.insights import InsightEngine
    from apps.engine.gating import IntelligenceGate

    can_view_actions = _user_has_feature(request.user, FeatureFlag.VIEW_ACTIONS)
    can_view_revenue_gap = _user_has_feature(request.user, FeatureFlag.VIEW_REVENUE_GAP)
    can_view_forecast = _user_has_feature(request.user, FeatureFlag.VIEW_FORECAST)

    if can_view_actions:
        decisions = get_top_priorities(request.user.id, limit=1)
        if decisions:
            d   = decisions[0]
            p   = d.product
            imp = {}
            lost = getattr(d, "estimated_lost_sales", 0) or 0
            rev  = getattr(d, "estimated_revenue_loss", 0) or 0
            if lost > 0 and can_view_revenue_gap:
                imp = {
                    "visible":          True,
                    "lost_sales_units": round(lost, 1),
                    "revenue_loss":     round(rev, 2),
                    "has_revenue":      rev > 0,
                }
            return Response({
                "source":   "decision_engine",
                "insight": {
                    "product_id":     str(p.id),
                    "product_sku":    p.sku,
                    "product_name":   p.name,
                    "observation":    d.reasoning.split(".")[0] + ".",
                    "prediction":     _days_to_prediction(d) if can_view_forecast else "Attention is needed soon.",
                    "recommendation": _action_to_recommendation(d),
                    "impact":         _impact_to_sentence(imp) if can_view_revenue_gap else "",
                    "confidence":     d.confidence_score,
                    "date_signal":    _days_to_date_signal(d),
                    "severity":       d.severity,
                    "urgency_tier":   d.severity,
                    "impact_detail":  imp,
                    "is_pro_detail":  can_view_forecast,
                    "priority_score": d.priority_score,
                }
            })

    # Free users or no active decisions — fall back to InsightEngine
    engine  = InsightEngine()
    insight = engine.get_dominant_insight(request.user)

    if not insight:
        return Response({"insight": None})

    gate  = IntelligenceGate()
    # Approximate dates for free users
    import re
    prediction = re.sub(r"in ~\d+ days \([^)]+\)", "soon", insight.prediction)

    return Response({
        "source":  "insight_engine",
        "insight": {
            "product_id":     insight.product_id,
            "product_sku":    insight.product_sku,
            "product_name":   insight.product_name,
            "observation":    insight.observation,
            "prediction":     prediction,
            "recommendation": insight.recommendation,
            "impact":         "",
            "confidence":     insight.confidence,
            "date_signal":    "soon",
            "severity":       insight.severity,
            "urgency_tier":   insight.urgency_tier,
            "impact_detail":  {"visible": False},
            "is_pro_detail":  False,
        }
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_trust_moment(request):
    resolved = (
        ForecastSnapshot.objects
        .filter(
            product__owner=request.user,
            actual_quantity__isnull=False,
        )
        .select_related("product")
        .order_by("-forecast_date")
        .first()
    )

    if not resolved or resolved.actual_quantity in [None, 0]:
        return Response(None, status=status.HTTP_200_OK)

    predicted = float(resolved.predicted_quantity or 0.0)
    actual = float(resolved.actual_quantity or 0.0)
    abs_pct_error = abs(float(resolved.forecast_error or 0.0)) / max(actual, 1.0)
    accuracy_pct = round(max(0.0, min(100.0, (1.0 - abs_pct_error) * 100.0)), 1)

    decision = (
        DecisionLog.objects
        .filter(
            product=resolved.product,
            forecast=resolved,
        )
        .order_by("-created_at")
        .first()
    )

    predicted_days = None
    if decision and decision.days_remaining_at_decision is not None:
        predicted_days = max(1, round(decision.days_remaining_at_decision))

    actual_days = predicted_days
    if decision and decision.created_at:
        actual_days = max(1, (resolved.forecast_date - decision.created_at.date()).days)

    return Response({
        "product_name": resolved.product.name,
        "product_sku": resolved.product.sku,
        "predicted_days": predicted_days,
        "actual_days": actual_days,
        "accuracy_pct": accuracy_pct,
        "forecast_date": resolved.forecast_date,
    })


# ── Helpers for Pro decision → display format ──────────────────────

def _days_to_prediction(d) -> str:
    days = getattr(d, "days_remaining_at_decision", None)
    if not days:
        return "Stock levels are approaching a critical threshold."
    conf = d.confidence_score
    if conf >= 0.70:
        return f"Stock is expected to run out in approximately {days:.0f} days."
    return f"Stock may run out in approximately {days:.0f} days."


def _days_to_date_signal(d) -> str:
    from apps.engine.reasoning import DatePrecisionEngine
    days = getattr(d, "days_remaining_at_decision", None)
    return DatePrecisionEngine().format(days, d.confidence_score)


def _action_to_recommendation(d) -> str:
    from apps.inventory.models import DecisionLog
    labels = {
        DecisionLog.ALERT_CRITICAL: f"Reorder {d.product.name} urgently to avoid a stockout.",
        DecisionLog.ALERT_LOW:      f"Schedule a reorder for {d.product.name} this week.",
        DecisionLog.REORDER:        f"Place a reorder for {d.product.name} soon.",
        DecisionLog.CHECK_STOCK:    f"Do a physical count of {d.product.name} to verify stock.",
        DecisionLog.MONITOR:        f"Keep an eye on {d.product.name} over the next few days.",
        DecisionLog.HOLD:           f"No immediate action needed for {d.product.name}.",
    }
    return labels.get(d.action, f"Review {d.product.name} at your next opportunity.")


def _impact_to_sentence(imp: dict) -> str:
    if not imp.get("visible"):
        return ""
    lost = imp.get("lost_sales_units", 0)
    rev  = imp.get("revenue_loss", 0)
    if rev > 0:
        return (
            f"If not addressed, you may lose approximately "
            f"{lost:.0f} units in sales (~₦{rev:,.0f} in revenue)."
        )
    return f"If not addressed, you may miss approximately {lost:.0f} sales of this product."


def _get_product(product_id: str):
    """Helper to fetch a product for gating context."""
    try:
        from apps.inventory.models import Product
        return Product.objects.get(id=product_id)
    except Exception:
        return None


# backend/apps/api/views.py — ADD

@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    GET  /api/v1/profile/   — return full profile
    PATCH /api/v1/profile/  — update profile fields
    """
    user = request.user
    if request.method == "GET":
        _maybe_send_automated_product_update_reminder(user)
        telegram_profile = getattr(user, "telegram_profile", None)
        telegram_linked = bool(telegram_profile and getattr(telegram_profile, "is_active", False))
        return Response({
            "id":                           str(user.id),
            "username":                     user.username,
            "email":                        user.email,
            "business_name":                user.business_name,
            "business_type":                user.business_type,
            "country":                      user.country,
            "currency":                     user.currency,
            "phone_number":                 user.phone_number,
            "whatsapp_enabled":             False,
            "telegram_enabled":             user.telegram_enabled,
            "telegram_linked":              telegram_linked,
            "preferred_channel":            user.CHANNEL_EMAIL if user.preferred_channel == "whatsapp" else user.preferred_channel,
            "whatsapp_critical_only":       False,
            "email_notifications_enabled":  user.email_notifications_enabled,
            "avatar_url":                   user.avatar_url,
            "tier":                         user.current_plan,
            "is_pro":                       user.is_pro,
            "date_joined":                  user.date_joined,
            "telegram_download_url":        "https://telegram.org/dl",
        })

    # PATCH — update allowed fields
    allowed = [
        "business_name", "business_type", "phone_number",
        "email_notifications_enabled", "avatar_url",
        "telegram_enabled", "preferred_channel", "country", "currency",
    ]
    telegram_profile = getattr(user, "telegram_profile", None)
    telegram_linked = bool(telegram_profile and getattr(telegram_profile, "is_active", False))
    if request.data.get("telegram_enabled") and not telegram_linked:
        return Response(
            {
                "detail": "Link your Telegram account before enabling Telegram notifications.",
                "telegram_download_url": "https://telegram.org/dl",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if request.data.get("preferred_channel") == user.CHANNEL_TELEGRAM and not telegram_linked:
        return Response(
            {
                "detail": "Telegram must be linked before it can be selected as your preferred channel.",
                "telegram_download_url": "https://telegram.org/dl",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    for field in allowed:
        if field in request.data:
            value = request.data[field]
            if field == "preferred_channel" and value == "whatsapp":
                value = user.CHANNEL_EMAIL
            if field == "country":
                value = _normalize_country(value)
            if field == "currency":
                continue
            setattr(user, field, value)
            if field == "country":
                user.currency = _currency_for_country(value)
    user.save()

    business = getattr(user, "business_profile", None)
    if business is not None:
        business.name = user.business_name or business.name
        business.country = user.country or business.country
        business.currency = user.currency or business.currency
        business.save()
    return Response({"status": "updated"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    """POST /api/v1/profile/password/"""
    user         = request.user
    old_password = request.data.get("old_password", "")
    new_password = request.data.get("new_password", "")

    if not user.check_password(old_password):
        return Response(
            {"detail": "Current password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjValError
        validate_password(new_password, user)
    except DjValError as e:
        return Response({"password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()
    return Response({"status": "password_changed"})


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    POST /api/v1/auth/forgot-password/
    Sends a password reset OTP to the user's email.
    """
    from django.contrib.auth import get_user_model
    from apps.core.models import OTPVerification
    from django.core.mail import send_mail
    from django.conf import settings as djsettings

    User  = get_user_model()
    email = request.data.get("email", "").strip()

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Don't reveal whether the email exists
        return Response({"status": "sent"})

    otp = OTPVerification.generate(user, OTPVerification.PURPOSE_PASSWORD)

    try:
        send_mail(
            subject="SiloXR - Password reset code",
            message=(
                f"Hi {user.username},\n\n"
                f"Your password reset code is: {otp.code}\n\n"
                f"This code expires in 10 minutes.\n\n"
                f"If you did not request this, ignore this email."
            ),
            from_email=djsettings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.error("Password reset email failed for %s: %s", email, exc, exc_info=True)

    return Response({"status": "sent"})


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    """
    POST /api/v1/auth/reset-password/
    { email, code, new_password }
    """
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError
    from apps.core.models import OTPVerification

    User  = get_user_model()
    email = request.data.get("email", "").strip()
    code  = request.data.get("code",  "").strip()
    new_pw = request.data.get("new_password", "")

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"detail": "Invalid."}, status=status.HTTP_400_BAD_REQUEST)

    otp = OTPVerification.objects.filter(
        user=user, purpose=OTPVerification.PURPOSE_PASSWORD, is_used=False
    ).order_by("-created_at").first()

    if not otp or not otp.verify(code):
        return Response(
            {"detail": "Invalid or expired code."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(new_pw, user)
    except DjangoValidationError as exc:
        return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_pw)
    user.save()
    return Response({"status": "password_reset"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_phone_otp(request):
    """
    POST /api/v1/profile/phone/send-otp/
    Sends an OTP to the user's phone number for WhatsApp verification.
    """
    return Response(
        {"detail": "WhatsApp setup is temporarily disabled."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def verify_phone_otp(request):
    """
    POST /api/v1/profile/phone/verify/
    { code: "123456" }
    """
    return Response(
        {"detail": "WhatsApp setup is temporarily disabled."},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )

# backend/apps/api/views.py — ADD

@api_view(["POST"])
@permission_classes([AllowAny])
def telegram_webhook(request):
    """
    POST /api/telegram/webhook/
    Receives Telegram bot updates.
    Signature verification via X-Telegram-Bot-Api-Secret-Token header.
    """
    from apps.notifications.telegram import process_webhook
    from django.conf import settings as djsettings

    secret = getattr(djsettings, "TELEGRAM_WEBHOOK_SECRET", "")
    if secret:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != secret:
            return HttpResponse(status=403)

    process_webhook(request.data)
    return HttpResponse(status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def telegram_link_token(request):
    """
    GET /api/v1/telegram/link/
    Generates a token the user sends to the bot to link their account.
    Returns the bot username and the deep link URL.
    """
    bot_user = _get_telegram_bot_username()
    if not bot_user:
        return Response(
            {"detail": "Telegram linking is not configured yet."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        from apps.notifications.telegram import generate_link_token

        token = generate_link_token(request.user)
    except Exception as exc:
        logger.error("Telegram link generation failed for %s: %s", request.user.username, exc, exc_info=True)
        return Response(
            {"detail": "Telegram linking is temporarily unavailable. Please try again shortly."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    link = f"https://t.me/{bot_user}?start={token}"

    return Response({
        "token":    token,
        "bot_user": bot_user,
        "link":     link,
        "expires_in_minutes": 30,
    })
