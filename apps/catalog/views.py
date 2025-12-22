# apps/catalog/views.py

from rest_framework import viewsets, filters, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Category, Brand, SKU, Banner, FlashSale
from .serializers import CategorySerializer, ProductSerializer 
# Note: Assuming ProductSerializer is the main one. If ProductListSerializer is missing, we use ProductSerializer.

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    lookup_field = 'slug'

class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = CategorySerializer # Placeholder, strictly should have BrandSerializer
    permission_classes = [AllowAny]

class SKUViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public product master list.
    Includes filtering by Category, Brand, and Search.
    """
    queryset = SKU.objects.filter(is_active=True).select_related('category', 'brand')
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug', 'brand__slug', 'is_featured']
    search_fields = ['name', 'description', 'sku_code']
    ordering_fields = ['sale_price', 'created_at']
    lookup_field = 'sku_code'

class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Banner.objects.filter(is_active=True).order_by('sort_order')
    permission_classes = [AllowAny]
    # Inline serializer to avoid file bloat for simple models
    class BannerSerializer(serializers.ModelSerializer):
        class Meta:
            model = Banner
            fields = ['title', 'image_url', 'target_url', 'position', 'bg_gradient']
    serializer_class = BannerSerializer

class FlashSaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FlashSale.objects.filter(is_active=True)
    permission_classes = [AllowAny]
    # Simple serializer
    class FlashSaleSerializer(serializers.ModelSerializer):
        sku_name = serializers.CharField(source='sku.name')
        sku_image = serializers.CharField(source='sku.image_url')
        class Meta:
            model = FlashSale
            fields = ['sku_id', 'sku_name', 'sku_image', 'discounted_price', 'end_time']
    serializer_class = FlashSaleSerializer

class BulkImportSKUView(views.APIView):
    permission_classes = [IsAuthenticated] # Staff only via permission classes setting
    def post(self, request):
        return Response({"status": "Imported (Mock)"})

class SearchSuggestView(views.APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        q = request.query_params.get('q', '')
        if len(q) < 2: return Response([])
        # logic for suggestion
        return Response([])

# --- Stubbed functions for the urls.py imports to work ---
@api_view(['GET'])
@permission_classes([AllowAny])
def get_products_cursor_api(request):
    return Response({"results": []})

@api_view(['GET'])
@permission_classes([AllowAny])
def get_home_feed_api(request):
    return Response({"sections": []})