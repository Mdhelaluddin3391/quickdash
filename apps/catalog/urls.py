# apps/catalog/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, 
    BrandViewSet, 
    SKUViewSet, 
    BulkImportSKUView,
    BannerViewSet,      # Ensure these are imported
    FlashSaleViewSet    # Ensure these are imported
)

# 1. Initialize Router
router = DefaultRouter()

# 2. Register ViewSets (Order matters slightly for readability)
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"skus", SKUViewSet, basename="sku")
router.register(r"banners", BannerViewSet, basename="banner")
router.register(r"flash-sales", FlashSaleViewSet, basename="flash-sale")

# 3. Define URL Patterns
urlpatterns = [
    # Router URLs include all the viewsets registered above
    path("", include(router.urls)),
    
    # Custom non-router paths
    path("import/bulk-csv/", BulkImportSKUView.as_view(), name="bulk-import-csv"),
]