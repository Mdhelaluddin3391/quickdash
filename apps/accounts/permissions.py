from rest_framework.permissions import BasePermission
from .models import EmployeeProfile


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, 'customer_profile')


class IsRider(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, 'rider_profile')


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(user and user.is_authenticated and user.is_staff)


def _get_employee_role(user):
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
        return _get_employee_role(request.user) == EmployeeProfile.Role.PICKER


class IsPackerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.PACKER


class IsAuditorEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.AUDITOR


class IsWarehouseManagerEmployee(BasePermission):
    def has_permission(self, request, view):
        role = _get_employee_role(request.user)
        return role in (EmployeeProfile.Role.MANAGER, EmployeeProfile.Role.SUPERVISOR, EmployeeProfile.Role.ADMIN)


class IsAdminEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == EmployeeProfile.Role.ADMIN
