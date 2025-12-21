# apps/accounts/permissions.py
from rest_framework import permissions

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'role', '') == 'CUSTOMER'

class WarehouseManagerOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        # Assuming EmployeeProfile model links user to role/warehouse
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, 'employee_profile', None)
        return profile and profile.role in ['MANAGER', 'ADMIN']

class PickerOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, 'employee_profile', None)
        return profile and profile.role in ['PICKER', 'MANAGER', 'ADMIN']

class PackerOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        profile = getattr(request.user, 'employee_profile', None)
        return profile and profile.role in ['PACKER', 'MANAGER', 'ADMIN']

class AnyEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and hasattr(request.user, 'employee_profile')