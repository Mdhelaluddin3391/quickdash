from rest_framework.permissions import BasePermission
from .models import EmployeeProfile


def _get_token_claim(request, key, default=None):
    """
    Helper: SimpleJWT token se claim (role, client) nikalta hai.
    """
    token = getattr(request, "auth", None)
    if not token:
        return default
    # SimpleJWT validated token behaves like dict
    try:
        return token.get(key, default)
    except AttributeError:
        # if it's not dict-like
        return getattr(token, key, default)


class RolePermission(BasePermission):
    """
    Base permission jo token mein 'role' aur 'client' check karta hai.
    Yeh Customer, Rider, aur Admin Panel ke liye hai.
    """
    required_role = None
    required_client = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = _get_token_claim(request, "role")
        client = _get_token_claim(request, "client")

        if self.required_role and role != self.required_role:
            return False
        if self.required_client and client != self.required_client:
            return False
        return True


# ========== App-Level Permissions (Pehle waale) ==========

class IsCustomer(RolePermission):
    required_role = "CUSTOMER"
    required_client = "customer_app"


class IsRider(RolePermission):
    required_role = "RIDER"
    required_client = "rider_app"


class IsAdmin(RolePermission):
    """
    Yeh permission Admin Panel (is_staff) login ke liye hai.
    """
    required_role = "ADMIN"
    required_client = "admin_panel"


# ========== Employee-Level Permissions (Naye waale) ==========

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
        return _get_employee_role(request.user) == "PICKER"


class IsPackerEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "PACKER"


class IsAuditorEmployee(BasePermission):
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "AUDITOR"


class IsWarehouseManagerEmployee(BasePermission):
    """
    Manager level access: MANAGER, SUPERVISOR, ya ADMIN employees
    """
    def has_permission(self, request, view):
        role = _get_employee_role(request.user)
        return role in ("MANAGER", "SUPERVISOR", "ADMIN")


class IsAdminEmployee(BasePermission):
    """
    Strict warehouse admin (jaise FC issue karna)
    """
    def has_permission(self, request, view):
        return _get_employee_role(request.user) == "ADMIN"