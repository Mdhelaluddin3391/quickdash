from rest_framework.permissions import BasePermission


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


class RolePermission(BasePermission):
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


class IsCustomer(RolePermission):
    required_role = "CUSTOMER"
    required_client = "customer_app"


class IsRider(RolePermission):
    required_role = "RIDER"
    required_client = "rider_app"


class IsEmployee(RolePermission):
    required_role = "EMPLOYEE"
    required_client = "employee_app"
