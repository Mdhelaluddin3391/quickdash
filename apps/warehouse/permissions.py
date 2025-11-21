# apps/warehouse/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS
from apps.accounts.permissions import (  # reuse central role logic
    IsEmployee,
    IsPickerEmployee,
    IsPackerEmployee,
    IsWarehouseManagerEmployee,
    IsAdminEmployee,
)


class IsWarehouseReadOnly(BasePermission):
    """
    Allow any authenticated user to READ warehouse structure.
    Write is handled per-view with stronger permissions.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return False


# aliases for readability inside WMS views
PickerOnly = IsPickerEmployee
PackerOnly = IsPackerEmployee
WarehouseManagerOnly = IsWarehouseManagerEmployee
AdminEmployeeOnly = IsAdminEmployee
AnyEmployee = IsEmployee
