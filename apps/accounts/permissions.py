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


from rest_framework.permissions import BasePermission


class IsPicker(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "picker"


class IsPacker(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "packer"


class IsWarehouseManager(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "manager"


class IsAuditor(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "auditor"


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"