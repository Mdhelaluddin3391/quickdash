# apps/accounts/permissions.py
from rest_framework.permissions import BasePermission
from .models import EmployeeProfile


class IsCustomer(BasePermission):
    """
    Checks if the user has a customer profile.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, 'customer_profile')


class IsRider(BasePermission):
    """
    Checks if the user has a rider profile.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, 'rider_profile')


class IsAdmin(BasePermission):
    """
    Admin Panel (is_staff) login.
    """
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)


# ========== Employee-Level Permissions (Warehouse / Ops) ==========

def _get_employee_role(user):
    """
    Helper: User ke active EmployeeProfile se role nikalta hai.
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
    """
    Check karta hai ki user ek active employee hai (kisi bhi role ka).
    """
    def has_permission(self, request, view):
        return _get_employee_role(request.user) is not None


class IsPickerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.PICKER


class IsPackerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.PACKER


class IsAuditorEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.AUDITOR


class IsWarehouseManagerEmployee(BasePermission):
    """
    Manager level access: MANAGER, SUPERVISOR, ya ADMIN employees
    """
    def has_permission(self, request, view):
        role = _get_employee_role(request.user)
        return role in (
            EmployeeProfile.Role.MANAGER,
            EmployeeProfile.Role.SUPERVISOR,
            EmployeeProfile.Role.ADMIN,
        )


class IsAdminEmployee(BasePermission):
    """
    Strict warehouse admin (jaise FC issue karna)
    """
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.ADMIN
