# apps/catalog/views.py

from rest_framework import viewsets, permissions, filters
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from django.utils import timezone
from django.contrib.postgres.search import TrigramSimilarity
import csv
from io import TextIOWrapper

from .models import Category, Brand, SKU, Banner, FlashSale
from .serializers import (
    CategorySerializer, BrandSerializer, SKUSerializer,
    BannerSerializer, FlashSaleSerializer
)

class ReadAnyWriteAdminMixin:
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
    serializer_class = SKUSerializer
    lookup_field = "sku_code"
    throttle_classes = []

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand__slug', 'is_featured', 'is_active']
    
    # FIX: Removed 'metadata__values' which causes 500 errors (invalid lookup).
    # If you need deep JSON search, use specific keys like 'metadata__color'.
    search_fields = ["name", "sku_code", "search_keywords"]
    
    ordering_fields = ["sale_price", "created_at", "name"]
    ordering = ["name"]

    def get_queryset(self):
        # Optimized queryset with select_related
        qs = SKU.objects.all().select_related("category", "brand")
        user = self.request.user

        if not user.is_authenticated or not user.is_staff:
            qs = qs.filter(
                is_active=True,
                category__is_active=True,
                brand__is_active=True,
            )

        category_slug = self.request.query_params.get('category__slug')
        if category_slug:
            # FIX: Use Q objects to filter parent or direct category in one query
            qs = qs.filter(
                Q(category__slug=category_slug) | 
                Q(category__parent__slug=category_slug)
            )

        return qs




class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Banner.objects.filter(is_active=True).order_by('sort_order')
    serializer_class = BannerSerializer
    permission_classes = [AllowAny]


class FlashSaleViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FlashSaleSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        now = timezone.now()
        return FlashSale.objects.filter(
            is_active=True, 
            start_time__lte=now, 
            end_time__gte=now
        ).select_related('sku').order_by('end_time')



class SearchSuggestView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if len(query) < 2:
            return Response([])

        categories = Category.objects.filter(
            Q(name__icontains=query) | Q(slug__icontains=query),
            is_active=True
        )[:3]

        cat_data = [{
            "type": "category",
            "text": c.name,
            "url": f"/search_results.html?slug={c.slug}",
            "icon": "fas fa-th-large"
        } for c in categories]

        try:
            products = SKU.objects.annotate(
                similarity=TrigramSimilarity('name', query)
            ).filter(
                Q(similarity__gt=0.1) | Q(name__icontains=query) | Q(sku_code__icontains=query),
                is_active=True
            ).order_by('-similarity')[:6]
        except Exception:
            products = SKU.objects.filter(
                name__icontains=query, 
                is_active=True
            )[:6]

        prod_data = [{
            "type": "product",
            "text": p.name,
            "sub_text": f"in {p.category.name if p.category else 'General'}",
            "url": f"/product.html?code={p.sku_code}",
            "image": p.image_url,
            "price": p.sale_price
        } for p in products]

        return Response(cat_data + prod_data)



class BulkImportSKUView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj or not file_obj.name.endswith('.csv'):
            return Response({"error": "CSV file required"}, status=400)

        try:
            csv_file = TextIOWrapper(file_obj.file, encoding='utf-8')
            reader = csv.DictReader(csv_file)
            count = 0
            
            for row in reader:
                cat_name = row.get('category', '').strip()
                brand_name = row.get('brand', '').strip()
                
                if cat_name and brand_name:
                    category, _ = Category.objects.get_or_create(name=cat_name)
                    brand, _ = Brand.objects.get_or_create(name=brand_name)
                    
                    SKU.objects.update_or_create(
                        sku_code=row.get('sku_code', '').strip(),
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

            return Response({"message": f"Processed {count} SKUs."}, status=200)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
