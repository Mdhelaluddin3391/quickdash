from django.contrib import admin
from .models import Category, Brand, SKU

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(SKU)
class SKUAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'name', 'category', 'brand', 'sale_price', 'is_active')
    search_fields = ('sku_code', 'name')
    list_filter = ('category', 'brand', 'is_active')
    list_editable = ('sale_price', 'is_active')