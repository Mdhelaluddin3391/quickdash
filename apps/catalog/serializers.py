# apps/catalog/serializers.py
from rest_framework import serializers
from .models import Category, Brand, SKU

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = '__all__'

class SKUSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)

    class Meta:
        model = SKU
        fields = [
            'id', 'sku_code', 'name', 
            'category', 'category_name',
            'brand', 'brand_name',
            'unit', 'sale_price', 'cost_price', 
            'image_url', 'is_active', 'metadata'
        ]
        extra_kwargs = {
            'category': {'write_only': True},
            'brand': {'write_only': True}
        }