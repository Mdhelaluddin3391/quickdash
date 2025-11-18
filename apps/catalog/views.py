# apps/catalog/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .models import Category, Brand, SKU
from .serializers import CategorySerializer, BrandSerializer, SKUSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

class BrandViewSet(viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'id'

class SKUViewSet(viewsets.ModelViewSet):
    queryset = SKU.objects.filter(is_active=True)
    serializer_class = SKUSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'sku_code' # SKU Code se fetch karna aasaan hoga (e.g. /api/v1/catalog/products/MILK-1L/)