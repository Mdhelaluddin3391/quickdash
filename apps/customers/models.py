from django.db import models
from django.conf import settings

class CustomerProfile(models.Model):
    """
    Extensions to the core Identity for buying behavior.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='customer_profile'
    )
    loyalty_points = models.IntegerField(default=0)
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customer: {self.user.phone_number}"

class Address(models.Model):
    """
    Saved delivery locations for the customer.
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
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_default', '-id']

    def __str__(self):
        return f"{self.label} - {self.address_line_1}"