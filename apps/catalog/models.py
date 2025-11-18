import uuid
from django.db import models

class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subcategories')

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Brand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name

class SKU(models.Model):
    """
    Stock Keeping Unit - Yeh hamara actual product hai.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku_code = models.CharField(max_length=100, unique=True, db_index=True) # e.g., 'MILK-1L-AMUL'
    name = models.CharField(max_length=255)
    
    # Relationships
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name='skus')
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.SET_NULL, related_name='skus')
    
    # Product Details
    unit = models.CharField(max_length=50, default='pcs')  # e.g., kg, ltr, pack
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # Customer price
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) # Purchase price
    
    # Meta info
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True) # Extra attributes like weight, dimensions
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sku_code} - {self.name}"