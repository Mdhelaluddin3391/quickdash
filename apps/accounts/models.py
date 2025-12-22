import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from .managers import UserManager

class Role(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    RIDER = "RIDER", "Rider"
    WAREHOUSE_MANAGER = "MANAGER", "Warehouse Manager"
    ADMIN = "ADMIN", "Admin"

class User(AbstractBaseUser, PermissionsMixin):
    """
    Core Identity Model. 
    Phone number is the primary identifier.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=15, unique=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, null=True)
    
    # Role context for the current session/primary usage
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.phone} ({self.role})"

class OTP(models.Model):
    """
    Secure OTP tracking with expiration and retry limits.
    """
    phone = models.CharField(max_length=15, db_index=True)
    code = models.CharField(max_length=6)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() > self.expires_at