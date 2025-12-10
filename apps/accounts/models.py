# apps/accounts/models.py
from django.db import models, transaction
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.gis.db import models as gis_models
from django.utils import timezone
from datetime import timedelta
import uuid
import secrets
from django.conf import settings
from .managers import UserManager
from apps.utils.models import TimestampedModel


# ==========================
# USER
# ==========================
class User(AbstractBaseUser, PermissionsMixin):
    """
    Core User:
    - phone-based login
    - NOTE: phone is NOT unique to allow multiple role-specific accounts
      for the same phone number (eg: customer + rider).
    - primary key is UUID
    - role flags: is_customer, is_rider, is_employee
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # IMPORTANT: do NOT set unique=True here if you want multiple accounts per phone
    phone = models.CharField(max_length=15, db_index=True)
    email = models.EmailField(null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)

    profile_picture = models.ImageField(
        upload_to='profile_pics/', null=True, blank=True
    )
    fcm_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="For push notifications",
    )

    # Optional high-level role tag (for admin/ACL convenience)
    app_role = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="High-level role tag for admin panels / ACL",
    )

    # ROLE FLAGS (fast lookup for business logic)
    is_customer = models.BooleanField(default=False, db_index=True)
    is_rider = models.BooleanField(default=False, db_index=True)
    is_employee = models.BooleanField(default=False, db_index=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        # return a readable identifier
        return self.phone or str(self.id)

    class Meta:
        indexes = [
            models.Index(fields=["phone"]),
            models.Index(fields=["is_customer"]),
            models.Index(fields=["is_rider"]),
            models.Index(fields=["is_employee"]),
        ]
        verbose_name = "User"
        verbose_name_plural = "Users"


# ==========================
# ADDRESS (CUSTOMER)
# ==========================
class Address(gis_models.Model):
    class AddressType(models.TextChoices):
        HOME = 'HOME', 'Home'
        WORK = 'WORK', 'Work'
        OTHER = 'OTHER', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.HOME,
    )

    full_address = models.TextField()
    landmark = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, db_index=True)

    # Lat/Long (GeoDjango Point)
    location = gis_models.PointField(srid=4326, null=True, blank=True)

    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # Ensure single default address per user
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(
                    user=self.user,
                    is_default=True,
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        phone = getattr(self.user, "phone", str(self.user))
        return f"{phone} - {self.full_address[:40]}..."

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"


# ==========================
# CUSTOMER PROFILE
# ==========================
class CustomerProfile(models.Model):
    """
    Customer-specific profile.
    OneToOne with a User instance that has is_customer=True.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )

    def __str__(self):
        return f"Customer({self.user.phone})"

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"


# ==========================
# RIDER PROFILE
# ==========================
class RiderProfile(TimestampedModel):
    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    class RiderStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACTIVE = "ACTIVE", "Active"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rider_profile',
    )
    rider_code = models.CharField(max_length=50, unique=True)

    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    status = models.CharField(
        max_length=16,
        choices=RiderStatus.choices,
        default=RiderStatus.PENDING,
    )

    current_location = gis_models.PointField(srid=4326, null=True, blank=True)
    last_location_update = models.DateTimeField(null=True, blank=True)

    on_duty = models.BooleanField(default=False, db_index=True)
    on_delivery = models.BooleanField(default=False, db_index=True)

    vehicle_type = models.CharField(max_length=32, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
    cash_on_hand = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Rider: {self.user.phone} ({self.status})"

    class Meta:
        verbose_name = "Rider Profile"
        verbose_name_plural = "Rider Profiles"


# ==========================
# EMPLOYEE PROFILE
# ==========================
class EmployeeProfile(models.Model):
    class Role(models.TextChoices):
        PICKER = "PICKER", "Picker"
        PACKER = "PACKER", "Packer"
        MANAGER = "MANAGER", "Manager"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        AUDITOR = "AUDITOR", "Auditor"
        ADMIN = "ADMIN", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_code = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=32, choices=Role.choices)

    warehouse_code = models.CharField(max_length=50)
    is_active_employee = models.BooleanField(default=True)

    last_task_assigned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Employee({self.employee_code} - {self.role})"

    class Meta:
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"


# ==========================
# PHONE OTP
# ==========================
class PhoneOTP(models.Model):
    class LoginType(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        EMPLOYEE = "EMPLOYEE", "Employee"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    phone = models.CharField(max_length=15, db_index=True)
    login_type = models.CharField(max_length=16, choices=LoginType.choices)
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
            # mark previous unused OTPs used
            cls.objects.filter(
                phone=phone,
                login_type=login_type,
                is_used=False,
            ).update(is_used=True)
            return cls.objects.create(
                phone=phone,
                login_type=login_type,
                otp_code=code,
                expires_at=expires_at,
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

    class Meta:
        indexes = [
            models.Index(fields=["phone", "login_type", "is_used"]),
        ]
        verbose_name = "Phone OTP"
        verbose_name_plural = "Phone OTPs"


# ==========================
# USER SESSION
# ==========================
class UserSession(models.Model):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        EMPLOYEE = "EMPLOYEE", "Employee"
        ADMIN_PANEL = "ADMIN_PANEL", "Admin Panel"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    client = models.CharField(max_length=255)

    jti = models.CharField(max_length=255, db_index=True)

    device_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def revoke(self):
        if not self.is_active:
            return
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    class Meta:
        indexes = [
            models.Index(fields=["user", "role", "client", "is_active"]),
            models.Index(fields=["jti"]),
        ]
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"


# ==========================
# PASSWORD RESET TOKEN
# ==========================
class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reset_tokens",
    )
    token = models.CharField(
        max_length=100,
        unique=True,
        default=secrets.token_urlsafe,
    )
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    @classmethod
    def create_token(cls, user, ttl_minutes=60):
        now = timezone.now()
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(
            user=user,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )

    def is_valid(self):
        return (not self.is_used) and (self.expires_at > timezone.now())

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"