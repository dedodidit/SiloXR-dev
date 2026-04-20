# backend/apps/api/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BusinessHealthViewSet,
    DashboardViewSet,
    DecisionViewSet,
    EventSyncViewSet,
    ForecastViewSet,
    PortfolioViewSet,
    ProductViewSet,
    ReorderRecordViewSet,
    change_password,
    coverage_status,
    forgot_password,
    get_dominant_insight,
    get_insights,
    get_nudges,
    get_trust_moment,
    login,
    mark_notifications_read,
    me,
    notifications,
    notification_status,
    profile,
    register,
    respond_to_nudge,
    reset_password,
    send_phone_otp,
    send_test_email,
    submit_insight_feedback,
    upload_data,
    upload_sample,
    verify_phone_otp,
)

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"events/sync", EventSyncViewSet, basename="event-sync")
router.register(r"decisions", DecisionViewSet, basename="decision")
router.register(r"forecasts", ForecastViewSet, basename="forecast")
router.register(r"dashboard", DashboardViewSet, basename="dashboard")
router.register(r"portfolio", PortfolioViewSet, basename="portfolio")
router.register(r"business-health", BusinessHealthViewSet, basename="business-health")
router.register(r"reorders", ReorderRecordViewSet, basename="reorder")

urlpatterns = [
    path("v1/", include(router.urls)),
    path("v1/notifications/", notifications, name="notifications"),
    path("v1/notifications/status/", notification_status, name="notifications-status"),
    path("v1/notifications/read/", mark_notifications_read, name="notifications-read"),
    path("v1/notifications/test-email/", send_test_email, name="notifications-test-email"),
    path("v1/auth/me/", me, name="me"),
    path("v1/auth/register/", register, name="register"),
    path("v1/auth/login/", login, name="login"),
    path("v1/auth/forgot-password/", forgot_password, name="forgot-password"),
    path("v1/auth/reset-password/", reset_password, name="reset-password"),
    path("v1/upload/", upload_data, name="upload"),
    path("v1/upload/sample/", upload_sample, name="upload-sample"),
    path("v1/nudge/", get_nudges, name="nudges"),
    path("v1/nudge/respond/", respond_to_nudge, name="nudge-respond"),
    path("v1/coverage/", coverage_status, name="coverage"),
    path("v1/insights/", get_insights, name="insights"),
    path("v1/insights/feedback/", submit_insight_feedback, name="insight-feedback"),
    path("v1/profile/", profile, name="profile"),
    path("v1/profile/password/", change_password, name="change-password"),
    path("v1/profile/phone/send-otp/", send_phone_otp, name="phone-otp-send"),
    path("v1/profile/phone/verify/", verify_phone_otp, name="phone-otp-verify"),
    path("v1/insights/dominant/", get_dominant_insight, name="insight-dominant"),
    path("v1/insights/trust-moment/", get_trust_moment, name="insight-trust-moment"),
]
