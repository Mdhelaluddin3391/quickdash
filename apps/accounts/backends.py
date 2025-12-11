from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class SuperAdminBackend(ModelBackend):
    """
    Strictly for Superadmin Login (Phone + Password).
    Ignores Customer/Rider accounts that might share the same phone number.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        try:
            # We filter for is_superuser=True to distinguish from regular users
            # who might share the same phone number
            user = User.objects.get(phone=username, is_superuser=True)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None