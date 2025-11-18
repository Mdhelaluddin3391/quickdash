# apps/inventory/urls.py
from django.urls import path
from .views import InventoryListAPIView, AdjustStockAPIView

urlpatterns = [
    # GET /api/v1/inventory/stock/
    path('stock/', InventoryListAPIView.as_view(), name='inventory-list'),
    
    # POST /api/v1/inventory/adjust/
    path('adjust/', AdjustStockAPIView.as_view(), name='inventory-adjust'),
]