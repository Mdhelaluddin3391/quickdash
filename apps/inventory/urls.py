from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InventoryStockViewSet,
    InventoryHistoryListAPIView,
    AdjustStockAPIView,
)

router = DefaultRouter()
router.register(r'stocks', InventoryStockViewSet, basename='inventory-stock')

urlpatterns = [
    path('', include(router.urls)),
    path('history/', InventoryHistoryListAPIView.as_view(), name='inventory-history'),
    path('adjust/', AdjustStockAPIView.as_view(), name='inventory-adjust'),
]