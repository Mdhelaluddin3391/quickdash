# apps/catalog/admin.py
from django.contrib import admin
from .models import Category, Brand, SKU


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "sort_order")
    list_filter = ("is_active", "parent")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("sort_order", "name")


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ("is_active",)


@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = (
        "sku_code",
        "name",
        "category",
        "brand",
        "sale_price",
        "is_active",
        "is_featured",
    )
    search_fields = ("sku_code", "name", "primary_barcode", "search_keywords")
    list_filter = ("category", "brand", "is_active", "is_featured")
    list_editable = ("sale_price", "is_active", "is_featured")
    readonly_fields = ("created_at", "updated_at")



# apps/catalog/admin.py (Append this)
from .models import Banner, FlashSale

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'position', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')

# @admin.register(FlashSale)
# class FlashSaleAdmin(admin.ModelAdmin):
#     list_display = ('sku', 'discounted_price', 'is_active', 'end_time', 'percentage_sold')



# apps/catalog/admin.py

@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ('sku', 'discounted_price', 'is_active', 'start_time', 'end_time', 'percentage_sold')
    # Ye line add karein:
    list_editable = ('is_active', 'end_time')