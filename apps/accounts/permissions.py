from rest_framework.permissions import BasePermission
from .models import Role

class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.role == Role.CUSTOMER
        )

class IsRider(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.role == Role.RIDER
        )

class IsManager(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.role == Role.WAREHOUSE_MANAGER
        )