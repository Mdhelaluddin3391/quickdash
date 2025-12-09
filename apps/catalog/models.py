# apps/catalog/models.py
import uuid
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """
    Product category tree (e.g. Dairy > Milk > Toned Milk)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='subcategories',
    )
   
    # New fields
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    icon_url = models.URLField(null=True, blank=True)

    def get_all_children(self):
        return self.subcategories.all()

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["sort_order", "name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["parent", "sort_order"]),
            models.Index(fields=["is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="uniq_category_per_parent_name",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # FIX: Optimized slug generation
        if not self.slug:
            base_slug = slugify(self.name)
            slug_candidate = base_slug
            counter = 1
            
            # Check existence efficiently
            while Category.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
                slug_candidate = f"{base_slug}-{counter}"
                counter += 1
                
            self.slug = slug_candidate
        super().save(*args, **kwargs)


class Brand(models.Model):
    """
    Brand (Amul, Nestle, Britannia, etc.)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)

    # New fields
    is_active = models.BooleanField(default=True)
    logo_url = models.URLField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Brand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class SKU(models.Model):
    """
    Stock Keeping Unit - actual sellable item.

    NOTE:
    - Orders, Inventory, WMS sab yahi SKU model use karte hain.
    - Existing fields (sku_code, name, sale_price, cost_price, image_url, is_active, metadata)
      bacche rakhe gaye hain for compatibility. :contentReference[oaicite:1]{index=1}
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identifiers
    sku_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Human-readable code (e.g. MILK-1L-AMUL)",
    )
    primary_barcode = models.CharField(
        max_length=32,
        blank=True,
        help_text="EAN/UPC or primary barcode (optional)",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Relationships
    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='skus',
    )
    brand = models.ForeignKey(
        Brand,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='skus',
    )

    # Product Details
    unit = models.CharField(
        max_length=50,
        default='pcs',
        help_text="Unit like pcs, kg, g, ltr, ml, pack",
    )
    sale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Customer-facing selling price",
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Internal purchase cost price",
    )

    max_order_qty = models.PositiveIntegerField(
        default=20,
        help_text="Max quantity allowed per order",
    )
    min_order_qty = models.PositiveIntegerField(
        default=1,
        help_text="Minimum quantity per order",
    )

    # Tax / compliance
    hsn_code = models.CharField(max_length=32, blank=True)
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="GST percentage (e.g. 5.00 for 5%)",
    )

    # Meta info
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_returnable = models.BooleanField(default=True)

    weight_grams = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Weight in grams (for logistics)",
    )
    volume_ml = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Volume in ml (if applicable)",
    )
    shelf_life_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Shelf life in days (optional)",
    )

    search_keywords = models.TextField(
        blank=True,
        help_text="Space/comma separated extra search keywords",
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extra attributes like pack_type, flavor, etc.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "category"]),
            models.Index(fields=["is_active", "brand"]),
            models.Index(fields=["sale_price"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.sku_code} - {self.name}"




# apps/catalog/models.py (Append this)

class Banner(models.Model):
    """
    Dynamic Banners for Home Page (Hero Slider & Mid Banners)
    """
    POSITION_CHOICES = [
        ('HERO', 'Hero Slider'),
        ('MID', 'Middle Banner'),
    ]
    
    title = models.CharField(max_length=100)
    image_url = models.URLField(help_text="External URL or Cloudinary link")
    target_url = models.CharField(max_length=255, help_text="/category.html?slug=veg or /product.html?code=...")
    position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='HERO')
    bg_gradient = models.CharField(max_length=50, default="linear-gradient(135deg, #32CD32 0%, #2ecc71 100%)", help_text="CSS Gradient string")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.position} - {self.title}"


class FlashSale(models.Model):
    """
    Deal of the Day / Flash Sales
    """
    sku = models.OneToOneField('SKU', on_delete=models.CASCADE)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_quantity = models.PositiveIntegerField(default=100)
    sold_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Flash Sale: {self.sku.sku_code}"

    @property
    def percentage_sold(self):
        if self.total_quantity == 0: return 0
        return int((self.sold_quantity / self.total_quantity) * 100)
    
    @property
    def discount_percent(self):
        if self.sku.sale_price == 0: return 0
        diff = self.sku.sale_price - self.discounted_price
        return int((diff / self.sku.sale_price) * 100)