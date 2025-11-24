# apps/catalog/views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAdminUser

from .models import Category, Brand, SKU
from .serializers import CategorySerializer, BrandSerializer, SKUSerializer


class ReadAnyWriteAdminMixin:
    """
    GET / HEAD / OPTIONS => public (AllowAny)
    POST / PUT / PATCH / DELETE => staff/admin only
    """

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdminUser()]


class CategoryViewSet(ReadAnyWriteAdminMixin, viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = "slug"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["sort_order", "name"]
    ordering = ["sort_order", "name"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Public ke liye sirf active categories
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            qs = qs.filter(is_active=True)
        return qs


class BrandViewSet(ReadAnyWriteAdminMixin, viewsets.ModelViewSet):
    queryset = Brand.objects.all()
    serializer_class = BrandSerializer
    lookup_field = "slug"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_authenticated or not self.request.user.is_staff:
            qs = qs.filter(is_active=True)
        return qs


class SKUViewSet(ReadAnyWriteAdminMixin, viewsets.ModelViewSet):
    """
    Product / SKU API:

    - Anonymous / customer:
        - only active SKUs
        - active category/brand
    - Staff:
        - can see/manage all
    """

    serializer_class = SKUSerializer
    lookup_field = "sku_code"

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "sku_code", "search_keywords", "metadata"]
    ordering_fields = ["sale_price", "created_at", "name"]
    ordering = ["name"]

    def get_queryset(self):
        qs = SKU.objects.all().select_related("category", "brand")
        user = self.request.user

        if not user.is_authenticated or not user.is_staff:
            qs = qs.filter(
                is_active=True,
                category__is_active=True,
                brand__is_active=True,
            )
        return qs
