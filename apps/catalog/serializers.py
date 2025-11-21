# apps/catalog/serializers.py
from rest_framework import serializers
from .models import Category, Brand, SKU


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "parent",
            "is_active",
            "sort_order",
            "icon_url",
            "subcategories",
        ]

    def get_subcategories(self, obj):
        qs = obj.subcategories.filter(is_active=True).order_by("sort_order", "name")
        return CategorySerializer(qs, many=True, context=self.context).data


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "is_active", "logo_url"]


class SKUSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    brand_name = serializers.CharField(source="brand.name", read_only=True)

    class Meta:
        model = SKU
        fields = [
            "id",
            "sku_code",
            "primary_barcode",
            "name",
            "description",
            "category",
            "category_name",
            "brand",
            "brand_name",
            "unit",
            "sale_price",
            "cost_price",
            "max_order_qty",
            "min_order_qty",
            "hsn_code",
            "tax_rate",
            "image_url",
            "is_active",
            "is_featured",
            "is_returnable",
            "weight_grams",
            "volume_ml",
            "shelf_life_days",
            "search_keywords",
            "metadata",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "category": {"write_only": True, "required": False, "allow_null": True},
            "brand": {"write_only": True, "required": False, "allow_null": True},
        }
