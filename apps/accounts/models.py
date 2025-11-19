from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.gis.db import models as gis_models  # <-- GeoDjango Magic
from django.utils import timezone
from datetime import timedelta
import uuid
from .managers import UserManager
from django.db import transaction
from django.conf import settings

class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        EMPLOYEE = "EMPLOYEE", "Employee"
        ADMIN = "ADMIN", "Admin"

    phone = models.CharField(max_length=15, unique=True, db_index=True)
    email = models.EmailField(null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    fcm_token = models.CharField(max_length=255, null=True, blank=True, help_text="For Push Notifications")

    is_customer = models.BooleanField(default=False)
    is_rider = models.BooleanField(default=False)
    is_employee = models.BooleanField(default=False)

    app_role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.phone


class Address(gis_models.Model):
    class AddressType(models.TextChoices):
        HOME = 'HOME', 'Home'
        WORK = 'WORK', 'Work'
        OTHER = 'OTHER', 'Other'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=10, choices=AddressType.choices, default=AddressType.HOME)
    
    full_address = models.TextField()
    landmark = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, db_index=True)
    
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_default:
            with transaction.atomic():
                Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")

    def __str__(self):
        return f"Customer({self.user.phone})"

class EmployeeProfile(models.Model):
    class Role(models.TextChoices):
        PICKER = "PICKER", "Picker"
        PACKER = "PACKER", "Packer"
        MANAGER = "MANAGER", "Manager"
        ADMIN = "ADMIN", "Admin"
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employee_profile")
    employee_code = models.CharField(max_length=50, unique=True)
    role = models.CharField(max_length=32, choices=Role.choices)
    
    warehouse_code = models.CharField(max_length=50)
    is_active_employee = models.BooleanField(default=True)
    
    last_task_assigned_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Employee({self.employee_code} - {self.role})"


class PhoneOTP(models.Model):
    class LoginType(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        RIDER = "RIDER", "Rider"
        EMPLOYEE = "EMPLOYEE", "Employee"

    phone = models.CharField(max_length=15)
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
    ip_address = models.GenericIPAddressField(null=True, blank=True)
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
