# apps/warehouse/permissions.py
from rest_framework import permissions


class IsWarehouseManagerOrReadOnly(permissions.BasePermission):
    """
    Read-only for everyone authenticated, write for managers.
    For now: treat `is_staff` as warehouse manager.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_staff)
