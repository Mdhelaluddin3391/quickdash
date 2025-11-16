from rest_framework import permissions

class IsWarehouseManagerOrReadOnly(permissions.BasePermission):
    """
    Read-only for regular users, write for warehouse managers (example).
    Adjust to your project's role system.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        # simple placeholder: staff users are managers
        return bool(request.user and request.user.is_staff)
