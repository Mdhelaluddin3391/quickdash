from rest_framework.permissions import BasePermission

ffrom rest_framework.permissions import BasePermission
from .models import EmployeeProfile


def _get_token_claim(request, key, default=None):
    token = getattr(request, "auth", None)
    if not token:
        return default
    # SimpleJWT validated token behaves like dict
    try:
        return token.get(key, default)
    except AttributeError:
        # if it's not dict-like
        return getattr(token, key, default)



def _get_employee_role(user):
    """
    Helper: safe way to get employee role or None
    """
    if not user or not user.is_authenticated:
        return None
    try:
        profile = user.employee_profile
    except EmployeeProfile.DoesNotExist:
        return None
    if not profile.is_active_employee:
        return None
    return profile.role


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) is not None


class IsPickerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "PICKER"


class IsPackerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "PACKER"


class IsAuditorEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "AUDITOR"


class IsWarehouseManagerEmployee(BasePermission):
    """
    Manager level access: MANAGER or SUPERVISOR or ADMIN employees
    """
    def has_permission(self, request, view):
        role = _get_employee_role(request.user)
        return role in ("MANAGER", "SUPERVISOR", "ADMIN")


class IsAdminEmployee(BasePermission):
    """
    Strict admin, warehouse-level
    """
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "ADMIN"
