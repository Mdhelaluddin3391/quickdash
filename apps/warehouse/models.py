from django.db import models

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    address = models.TextField()
    
    # Geospatial Fields for Serviceability
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.FloatField(default=5.0, help_text="Serviceable radius in Kilometers")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name