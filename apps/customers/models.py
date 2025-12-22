from django.db import models
from django.conf import settings
from apps.utils.models import TimestampedModel

class CustomerProfile(TimestampedModel):
    """
    Customer-specific domain data.
    Linked 1:1 with the Auth User.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='customer_profile'
    )
    loyalty_points = models.IntegerField(default=0)
    preferences = models.JSONField(default=dict, blank=True, help_text="User preferences like notification settings, dietary, etc.")

    def __str__(self):
        return f"Customer: {self.user.phone}"

class Address(TimestampedModel):
    """
    Delivery addresses.
    """
    LABEL_CHOICES = (
        ('HOME', 'Home'),
        ('WORK', 'Work'),
        ('OTHER', 'Other'),
    )

    customer = models.ForeignKey(
        CustomerProfile, 
        on_delete=models.CASCADE, 
        related_name='addresses'
    )
    label = models.CharField(max_length=20, choices=LABEL_CHOICES, default='HOME')
    
    # Address details
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10, db_index=True)
    
    # Geospatial data (Decimal for simple lat/lng storage)
    # Note: Use PostGIS PointField in apps/warehouse for complex queries, 
    # but simple decimals are often sufficient for address storage.
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', '-created_at']
        verbose_name = "Address"
        verbose_name_plural = "Addresses"

    def __str__(self):
        return f"{self.label} - {self.city} ({self.pincode})"