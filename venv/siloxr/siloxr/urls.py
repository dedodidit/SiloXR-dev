# backend/siloxr/urls.py

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path("admin/",            admin.site.urls),
    path("api/",              include("apps.api.urls")),
    path("api/v1/billing/",   include("apps.billing.urls")),
    path("auth/",             include("rest_framework.urls")),
    path("api/token/",        TokenObtainPairView.as_view(),  name="token_obtain"),
    path("api/token/refresh/", TokenRefreshView.as_view(),   name="token_refresh"),
    path("api/token/verify/",  TokenVerifyView.as_view(),    name="token_verify"),
]
