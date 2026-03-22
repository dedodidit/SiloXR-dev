# backend/apps/api/permissions.py

from rest_framework.permissions import BasePermission, IsAuthenticated


class IsOwner(BasePermission):
    """
    Object-level permission: only the owner of the object can access it.
    Assumes the model has an `owner` field pointing to AUTH_USER_MODEL.
    """
    def has_object_permission(self, request, view, obj):
        return obj.owner == request.user


class IsProUser(BasePermission):
    """
    Endpoint-level gate for PRO-tier features.
    Returns HTTP 402 with a structured upgrade prompt instead of 403
    so the frontend can render an upgrade CTA rather than a generic error.
    """
    message = {
        "error": "pro_required",
        "detail": (
            "This feature requires a SiloXR Pro subscription. "
            "Upgrade to access predictions, decisions, and alerts."
        ),
        "upgrade_url": "/billing/upgrade/",
    }

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_pro
        )


class IsOwnerOrReadOnly(BasePermission):
    """
    Allows read access to authenticated users,
    write access only to the object owner.
    """
    def has_object_permission(self, request, view, obj):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        return obj.owner == request.user