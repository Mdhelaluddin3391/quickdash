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
from django.db.models import UniqueConstraint, Q
from django.db import models
from django.conf import settings

# ==========================
# USER (The Identity)
# ==========================
class User(AbstractBaseUser, PermissionsMixin):
    """
    Multi-Role User Model.
    - USERNAME_FIELD = 'phone' (Required for Admin Panel login)
    - phone is NOT unique globally (One phone -> Customer, Rider, Employee)
    - id is UUID (Primary Key)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Phone is indexed but NOT unique to allow multiple roles per number
    phone = models.CharField(max_length=15, db_index=True) 
    email = models.EmailField(null=True, blank=True, db_index=True)
    full_name = models.CharField(max_length=255, blank=True)

    # Flags to quickly identify available profiles
    is_customer = models.BooleanField(default=False, db_index=True)
    is_rider = models.BooleanField(default=False, db_index=True)
    is_employee = models.BooleanField(default=False, db_index=True)

    # Current app role context (optional, mostly for frontend state)
    app_role = models.CharField(max_length=32, null=True, blank=True)

    profile_picture = models.ImageField(upload_to="profile_pics/", null=True, blank=True)
    fcm_token = models.CharField(max_length=255, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False) # True for Admin/Employee accessing Admin Panel
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = [] 

    objects = UserManager()

    current_session_jti = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="Tracks the JWT ID of the currently active session"
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        constraints = [
            UniqueConstraint(
                fields=['phone'], 
                condition=Q(is_superuser=True), 
                name='unique_superuser_phone'
            )
        ]

    def __str__(self):
        roles = []
        if self.is_superuser: roles.append("SuperUser")
        if self.is_customer: roles.append("Customer")
        if self.is_rider: roles.append("Rider")
        if self.is_employee: roles.append("Employee")
        return f"{self.phone} - {', '.join(roles)} ({self.id})"


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
    
    # GIS PointField (Source of Truth for distance calculation)
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(
                    user=self.user,
                    is_default=True,
                ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.phone} - {self.address_type}"

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"


# ==========================
# PROFILES
# ==========================
class CustomerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")

    def __str__(self):
        return f"Customer: {self.user.phone}"

    class Meta:
        verbose_name = "Customer Profile"
        verbose_name_plural = "Customer Profiles"


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
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rider_profile')
    rider_code = models.CharField(max_length=50, unique=True)
    
    approval_status = models.CharField(max_length=10, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    status = models.CharField(max_length=16, choices=RiderStatus.choices, default=RiderStatus.PENDING)

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


class EmployeeProfile(models.Model):
    class Role(models.TextChoices):
        PICKER = "PICKER", "Picker"
        PACKER = "PACKER", "Packer"
        MANAGER = "MANAGER", "Manager"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        AUDITOR = "AUDITOR", "Auditor"
        ADMIN = "ADMIN", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employee_profile")
    employee_code = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=32, choices=Role.choices)
    warehouse_code = models.CharField(max_length=50)
    is_active_employee = models.BooleanField(default=True)
    last_task_assigned_at = models.DateTimeField(null=True, blank=True)

    def can_access_admin_panel(self):
        """Helper to determine if this employee can log into the staff portal via Google"""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER, self.Role.SUPERVISOR, self.Role.AUDITOR]

    def __str__(self):
        return f"Employee({self.employee_code} - {self.role})"

    class Meta:
        verbose_name = "Employee Profile"
        verbose_name_plural = "Employee Profiles"


# ==========================
# AUTHENTICATION MODELS
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
    @classmethod
    def create_otp(cls, phone, login_type, code, ttl_minutes=5):
        now = timezone.now()
        
        with transaction.atomic():
            # LOCKING: Lock the most recent OTP record for this phone to serialize checks.
            # If no record exists, the race window is negligible for the first ever request, 
            # but subsequent concurrent spam is blocked.
            last_otp = cls.objects.select_for_update().filter(
                phone=phone, login_type=login_type
            ).order_by('-created_at').first()

            # 1. Rate Limit: 1 request per 60 seconds (Strict DB enforcement)
            if last_otp and last_otp.created_at > now - timedelta(seconds=60):
                return None, "Please wait 60 seconds before requesting a new OTP."

            # 2. Rate Limit: Max 20 requests per hour
            one_hour_ago = now - timedelta(hours=1)
            # Use count() which is fast on indexed fields
            hourly_count = cls.objects.filter(
                phone=phone, created_at__gte=one_hour_ago
            ).count()
            
            if hourly_count >= 20:
                return None, "Too many OTP requests. Please try again later."

            expires_at = now + timedelta(minutes=ttl_minutes)
            
            # Invalidate previous unused OTPs
            cls.objects.filter(phone=phone, login_type=login_type, is_used=False).update(is_used=True)
            
            otp_obj = cls.objects.create(
                phone=phone,
                login_type=login_type,
                otp_code=code,
                expires_at=expires_at,
            )
            return otp_obj, None

    def is_valid(self, otp_code):
        now = timezone.now()
        if self.is_used: return False, "OTP already used"
        if self.expires_at < now: return False, "OTP expired"
        
        # FIX: Explicitly burn OTP if max attempts reached previously
        if self.attempts >= 5: 
            self.is_used = True
            self.save(update_fields=["is_used"])
            return False, "Too many attempts"
        
        if self.otp_code != otp_code:
            self.attempts += 1
            # FIX: Check limit again after increment to burn immediately on 5th fail
            if self.attempts >= 5:
                self.is_used = True
                self.save(update_fields=["attempts", "is_used"])
                return False, "Too many attempts"
            
            self.save(update_fields=["attempts"])
            return False, "Invalid OTP"
            
        return True, ""


class UserSession(models.Model):
    """
    Tracks active sessions for JWT invalidation and security
    """
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        EMPLOYEE = "EMPLOYEE", "Employee"
        ADMIN_PANEL = "ADMIN_PANEL", "Admin Panel" # For Staff/Superadmin on web

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    role = models.CharField(max_length=16, choices=Role.choices)
    
    jti = models.CharField(max_length=255, db_index=True, unique=True) # Unique JTI for blacklist
    
    client = models.CharField(max_length=255) # User-Agent
    device_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def revoke(self):
        if self.is_active:
            self.is_active = False
            self.revoked_at = timezone.now()
            self.save(update_fields=["is_active", "revoked_at"])

    class Meta:
        indexes = [models.Index(fields=["user", "role", "is_active"])]
        ordering = ['-created_at']
        verbose_name = "User Session"
        verbose_name_plural = "User Sessions"


class PasswordResetToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reset_tokens")
    token = models.CharField(max_length=100, unique=True, default=secrets.token_urlsafe)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    @classmethod
    def create_token(cls, user, ttl_minutes=60):
        now = timezone.now()
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(user=user, expires_at=now + timedelta(minutes=ttl_minutes))
    
    def is_valid(self):
        return (not self.is_used) and (self.expires_at > timezone.now())

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "Password Reset Tokens"