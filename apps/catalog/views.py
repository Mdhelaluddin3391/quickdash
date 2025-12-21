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
from django.db import transaction
import csv
from io import TextIOWrapper

# --- NEW IMPORTS FOR PERFORMANCE ---
from django.http import JsonResponse
from django.views.decorators.http import require_GET
# -----------------------------------

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
    
    search_fields = ["name", "sku_code", "search_keywords"]
    
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

        category_slug = self.request.query_params.get('category__slug')
        if category_slug:
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
            # Fallback if pg_trgm extension is not installed
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
            
            # FIX: Use atomic transaction to prevent partial imports on failure
            with transaction.atomic():
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
            return Response({"error": f"Import failed: {str(e)}"}, status=500)





# ==========================================
#  NEW HIGH-PERFORMANCE VIEWS (No DRF)
# ==========================================

@require_GET
def get_products_cursor_api(request):
    """
    Optimized Cursor-based pagination for Infinite Scroll (Product List).
    """
    try:
        LIMIT = 12
        cursor_timestamp = request.GET.get('cursor')
        category_slug = request.GET.get('category__slug') # Fix: match frontend param

        queryset = SKU.objects.filter(is_active=True).select_related('category', 'brand')

        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        if cursor_timestamp:
            queryset = queryset.filter(created_at__lt=cursor_timestamp)

        products = list(queryset.order_by('-created_at')[:LIMIT])

        data = []
        last_cursor = None
        for sku in products:
            data.append({
                'id': str(sku.id),
                'name': sku.name,
                'sku_code': sku.sku_code,
                'price': float(sku.sale_price),
                'image': sku.image_url if sku.image_url else '',
                'category': sku.category.name if sku.category else 'Uncategorized',
                'brand': sku.brand.name if sku.brand else '',
                'unit': sku.unit,
                'is_featured': sku.is_featured
            })
            last_cursor = sku.created_at.isoformat()

        return JsonResponse({
            'products': data,
            'next_cursor': last_cursor if len(products) == LIMIT else None,
            'has_more': len(products) == LIMIT
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# apps/catalog/views.py

# apps/catalog/views.py

@require_GET
def get_home_feed_api(request):
    """
    Optimized Home Feed: Loads Categories + Top Products in batches.
    UPDATED: Fetches products from Sub-categories too (Fix for empty shelves).
    """
    try:
        page = int(request.GET.get('page', 1))
        batch_size = 3
        offset = (page - 1) * batch_size
        
        # 1. Fetch Parent Categories
        categories = Category.objects.filter(
            parent__isnull=True, 
            is_active=True
        ).order_by('sort_order', 'name')[offset : offset + batch_size]
        
        feed_data = []
        
        for cat in categories:
            # 2. Fetch Products from Parent AND Sub-categories
            # Fix: Use Q object to check both (category=cat OR category__parent=cat)
            products = SKU.objects.filter(
                Q(category=cat) | Q(category__parent=cat),
                is_active=True
            ).select_related('category').order_by('-is_featured', '-created_at')[:10]
            
            # Agar abhi bhi products nahi hain, toh skip karein
            if not products: 
                continue

            product_list = [{
                'id': str(p.id),
                'name': p.name,
                'sku_code': p.sku_code,
                'price': float(p.sale_price),
                'unit': p.unit,
                'image': p.image_url if p.image_url else '', 
                'is_featured': p.is_featured
            } for p in products]

            feed_data.append({
                'category_name': cat.name,
                'category_slug': cat.slug,
                'products': product_list
            })

        # 3. Pagination Logic
        total_cats = Category.objects.filter(parent__isnull=True, is_active=True).count()
        has_more = (offset + batch_size) < total_cats

        return JsonResponse({
            'sections': feed_data,
            'has_more': has_more,
            'next_page': page + 1 if has_more else None
        })

    except Exception as e:
        print(f"Home Feed Error: {e}")
        return JsonResponse({'error': str(e)}, status=500)