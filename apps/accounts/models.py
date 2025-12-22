import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .managers import UserManager

class Role(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    RIDER = "RIDER", "Rider"
    EMPLOYEE = "EMPLOYEE", "Employee"
    ADMIN = "ADMIN", "Admin"

class User(AbstractBaseUser, PermissionsMixin):
    """
    Core Identity Model. 
    Phone number is the primary identifier.
    One User can have multiple roles assigned in AccountRole.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=15, unique=True, db_index=True)
    email = models.EmailField(blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True)
    
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.phone_number

class UserRole(models.Model):
    """
    Intersection table defining which roles a specific identity holds.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=Role.choices)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.phone_number} - {self.role}"

class OTPLog(models.Model):
    """
    Secure OTP tracking with expiration and usage flags.
    """
    phone_number = models.CharField(max_length=15, db_index=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50, default="LOGIN")
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at