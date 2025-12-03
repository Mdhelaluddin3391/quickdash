# apps/catalog/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, BrandViewSet, SKUViewSet, BulkImportSKUView 

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"skus", SKUViewSet, basename="sku")

urlpatterns = [
    path("", include(router.urls)),
    path("import/bulk-csv/", BulkImportSKUView.as_view(), name="bulk-import-csv"),
]