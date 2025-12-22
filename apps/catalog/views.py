from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Publicly accessible category list.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public product master list. 
    NOTE: This does NOT show stock. Stock is fetched via the Inventory API 
    based on the user's location/warehouse.
    """
    queryset = Product.objects.filter(is_active=True).select_related('category')
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['category']
    search_fields = ['name', 'description']



from rest_framework import viewsets
from .models import Product
from .serializers import ProductListSerializer

class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    # OLD: queryset = Product.objects.all()
    # NEW: Optimized QuerySet
    queryset = Product.objects.filter(is_active=True).select_related(
        'brand', 
        'category'
    ).prefetch_related(
        'variants',      # e.g., Sizes/Colors
        'tags'
    ).order_by('-created_at')
    
    serializer_class = ProductListSerializer
    
    def get_queryset(self):
        """
        Allow filtering without breaking optimizations
        """
        qs = super().get_queryset()
        category_id = self.request.query_params.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
        return qs