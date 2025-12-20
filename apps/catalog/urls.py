from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet,
    BrandViewSet,
    SKUViewSet,
    BulkImportSKUView,
    BannerViewSet,
    FlashSaleViewSet,
    SearchSuggestView,
    # New Function Imports (Explicitly imported to fix NameError)
    get_products_cursor_api,
    get_home_feed_api
)
from .views_assistant import ShoppingAssistantView

# 1. Initialize Router
router = DefaultRouter()

# 2. Register ViewSets
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"skus", SKUViewSet, basename="sku")
router.register(r"banners", BannerViewSet, basename="banner")
router.register(r"flash-sales", FlashSaleViewSet, basename="flash-sale")

# 3. Define URL Patterns
urlpatterns = [
    # Router URLs (Categories, Brands, SKUs, Banners, Flash Sales)
    path("", include(router.urls)),
    
    # Custom Endpoints
    path("import/bulk-csv/", BulkImportSKUView.as_view(), name="bulk-import-csv"),
    path("assistant/chat/", ShoppingAssistantView.as_view(), name="shopping-assistant"),
    path("suggest/", SearchSuggestView.as_view(), name="search-suggest"),
    
    # --- PERFORMANCE APIs (Optimized) ---
    path('api/products/feed/', get_products_cursor_api, name='api_products_feed'),
    path('api/home/feed/', get_home_feed_api, name='api_home_feed'),
]