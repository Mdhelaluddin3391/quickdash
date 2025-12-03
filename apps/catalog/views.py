# apps/catalog/views.py
from rest_framework import viewsets, permissions, filters
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend  # Ensure django-filter is installed

from .models import Category, Brand, SKU
from .serializers import CategorySerializer, BrandSerializer, SKUSerializer
# apps/catalog/views.py
import csv
from io import TextIOWrapper
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from .models import Category, Brand, SKU

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
        
    Supports filtering by:
    - category (slug) via ?category=slug
    - search via ?search=query
    """

    serializer_class = SKUSerializer
    lookup_field = "sku_code"

    # Added DjangoFilterBackend for field-based filtering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # Fields available for filtering
    filterset_fields = ['category__slug', 'brand__slug', 'is_featured', 'is_active']
    
    search_fields = ["name", "sku_code", "search_keywords", "metadata__values"]
    ordering_fields = ["sale_price", "created_at", "name"]
    ordering = ["name"]

    def get_queryset(self):
        qs = SKU.objects.all().select_related("category", "brand")
        user = self.request.user

        # Basic visibility filter
        if not user.is_authenticated or not user.is_staff:
            qs = qs.filter(
                is_active=True,
                category__is_active=True,
                brand__is_active=True,
            )
            
        return qs






class BulkImportSKUView(APIView):
    """
    Admin Only: Bulk Import SKUs via CSV upload.
    """
    permission_classes = [IsAdminUser] # Sirf Admin/Staff allow karein
    parser_classes = [MultiPartParser] # File upload ke liye zaroori hai

    def post(self, request):
        file_obj = request.FILES.get('file')
        
        if not file_obj:
            return Response({"error": "No file selected"}, status=400)

        if not file_obj.name.endswith('.csv'):
            return Response({"error": "Please upload a CSV file"}, status=400)

        try:
            # File ko text mode mein read karein
            csv_file = TextIOWrapper(file_obj.file, encoding='utf-8')
            reader = csv.DictReader(csv_file)
            
            count = 0
            errors = []

            for row_idx, row in enumerate(reader):
                try:
                    # 1. Category & Brand (Get or Create)
                    cat_name = row.get('category', '').strip()
                    brand_name = row.get('brand', '').strip()
                    
                    if not cat_name or not brand_name:
                        continue # Skip invalid rows

                    category, _ = Category.objects.get_or_create(name=cat_name)
                    brand, _ = Brand.objects.get_or_create(name=brand_name)
                    
                    # 2. Update or Create SKU
                    sku_code = row.get('sku_code', '').strip()
                    
                    obj, created = SKU.objects.update_or_create(
                        sku_code=sku_code,
                        defaults={
                            'name': row.get('name', ''),
                            'category': category,
                            'brand': brand,
                            'sale_price': row.get('price', 0.0),
                            'unit': row.get('unit', 'pcs'),
                            'is_active': True
                        }
                    )
                    count += 1
                except Exception as e:
                    errors.append(f"Row {row_idx + 1}: {str(e)}")

            return Response({
                "message": f"Successfully processed {count} SKUs.",
                "errors": errors
            }, status=200)

        except Exception as e:
            return Response({"error": f"CSV Error: {str(e)}"}, status=500)