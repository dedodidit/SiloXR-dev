# backend/apps/core/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "tier", "is_pro", "tier_expires_at", "is_staff")
    list_filter = ("tier", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SiloXR", {"fields": ("tier", "tier_expires_at")}),
    )