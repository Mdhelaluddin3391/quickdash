from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from datetime import timedelta

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)

    # role flags
    is_customer = models.BooleanField(default=False)
    is_rider = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)

    # standard django flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="customer_profile"
    )
    default_address = models.CharField(max_length=255, blank=True)
    total_orders = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"CustomerProfile({self.user.phone})"


class RiderProfile(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending Verification"),
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="rider_profile"
    )
    rider_code = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    vehicle_type = models.CharField(max_length=32, null=True, blank=True)
    on_duty = models.BooleanField(default=False)

    def __str__(self):
        return f"RiderProfile({self.rider_code})"


class EmployeeProfile(models.Model):
    ROLE_CHOICES = [
        ("PICKER", "Picker"),
        ("PACKER", "Packer"),
        ("SUPERVISOR", "Supervisor"),
        ("MANAGER", "Manager"),
        ("SUPPORT", "Support"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="employee_profile"
    )
    employee_code = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    warehouse_code = models.CharField(max_length=50)
    is_active_employee = models.BooleanField(default=True)

    def __str__(self):
        return f"Employee({self.employee_code} - {self.role})"


class PhoneOTP(models.Model):
    LOGIN_CHOICES = [
        ("CUSTOMER", "Customer"),
        ("RIDER", "Rider"),
        ("EMPLOYEE", "Employee"),
    ]

    phone = models.CharField(max_length=15)
    login_type = models.CharField(max_length=16, choices=LOGIN_CHOICES)
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["phone", "login_type", "created_at"]),
        ]

    def __str__(self):
        return f"OTP({self.phone}, {self.login_type}, {self.otp_code})"

    @classmethod
    def create_otp(cls, phone, login_type, code, ttl_minutes=5):
        now = timezone.now()
        return cls.objects.create(
            phone=phone,
            login_type=login_type,
            otp_code=code,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

    def is_valid(self, otp_code):
        now = timezone.now()
        if self.is_used:
            return False, "OTP already used"
        if self.expires_at < now:
            return False, "OTP expired"
        if self.attempts >= 5:
            return False, "Too many attempts"
        if self.otp_code != otp_code:
            self.attempts += 1
            self.save(update_fields=["attempts"])
            return False, "Invalid OTP"
        return True, ""


class UserSession(models.Model):
    """
    Har login ke liye ek session row – enterprise style tracking.
    Logout par isse inactivate + (optionally) blacklist bhi.
    """

    ROLE_CHOICES = PhoneOTP.LOGIN_CHOICES

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    client = models.CharField(max_length=32)  # customer_app / rider_app / employee_app / admin_panel

    jti = models.CharField(max_length=255, db_index=True)  # refresh token ID
    device_id = models.CharField(max_length=255, blank=True)
    device_model = models.CharField(max_length=255, blank=True)   # 👈 NEW
    os_version = models.CharField(max_length=100, blank=True)     # 👈 NEW
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session(user={self.user.phone}, role={self.role}, client={self.client})"

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])
