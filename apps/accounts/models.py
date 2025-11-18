from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from datetime import timedelta
import uuid
from .managers import UserManager
from django.db import transaction

USER_ROLE_CHOICES = [
    ("CUSTOMER", "Customer"),
    ("RIDER", "Rider"),
    ("EMPLOYEE", "Employee"),
    ("ADMIN", "Admin"),
]

class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)

    # Flags
    is_customer = models.BooleanField(default=False)
    is_rider = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)

    # Main App Role
    app_role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default="CUSTOMER")

    # Django required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    default_address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Customer({self.user.phone})"

class RiderProfile(models.Model):
    STATUS_CHOICES = [("PENDING", "Pending"), ("ACTIVE", "Active"), ("SUSPENDED", "Suspended")]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="rider_profile")
    rider_code = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    vehicle_type = models.CharField(max_length=32, null=True, blank=True)
    on_duty = models.BooleanField(default=False)

    def __str__(self):
        return f"Rider({self.rider_code})"

class EmployeeProfile(models.Model):
    ROLE_CHOICES = [
        ("PICKER", "Picker"), ("PACKER", "Packer"), ("AUDITOR", "Auditor"),
        ("SUPERVISOR", "Supervisor"), ("MANAGER", "Manager"), ("ADMIN", "Admin")
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee_profile")
    employee_code = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    warehouse_code = models.CharField(max_length=50)
    is_active_employee = models.BooleanField(default=True)

    def __str__(self):
        return f"Employee({self.employee_code} - {self.role})"

class PhoneOTP(models.Model):
    LOGIN_CHOICES = [("CUSTOMER", "Customer"), ("RIDER", "Rider"), ("EMPLOYEE", "Employee")]
    phone = models.CharField(max_length=15)
    login_type = models.CharField(max_length=16, choices=LOGIN_CHOICES)
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create_otp(cls, phone, login_type, code, ttl_minutes=5):
        now = timezone.now()
        expires_at = now + timedelta(minutes=ttl_minutes)
        with transaction.atomic():
            cls.objects.filter(phone=phone, login_type=login_type, is_used=False).update(is_used=True)
            return cls.objects.create(phone=phone, login_type=login_type, otp_code=code, expires_at=expires_at)

    def is_valid(self, otp_code):
        now = timezone.now()
        if self.is_used: return False, "OTP already used"
        if self.expires_at < now: return False, "OTP expired"
        if self.attempts >= 5: return False, "Too many attempts"
        if self.otp_code != otp_code:
            self.attempts += 1
            self.save(update_fields=["attempts"])
            return False, "Invalid OTP"
        return True, ""

class UserSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    role = models.CharField(max_length=16)
    client = models.CharField(max_length=32)
    jti = models.CharField(max_length=255, db_index=True)
    device_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True) # <-- Naya Field Add Kiya
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    @classmethod
    def create_token(cls, user, ttl_minutes=60):
        now = timezone.now()
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(user=user, expires_at=now + timedelta(minutes=ttl_minutes))

    def is_valid(self):
        return not self.is_used and self.expires_at > timezone.now()