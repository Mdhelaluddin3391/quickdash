# apps/inventory/urls.py
from django.urls import path

from .views import (
    InventoryListAPIView,
    InventoryHistoryListAPIView,
    AdjustStockAPIView,
)

urlpatterns = [
    # GET /api/v1/inventory/stock/
    path("stock/", InventoryListAPIView.as_view(), name="inventory-list"),

    # GET /api/v1/inventory/history/
    path(
        "history/",
        InventoryHistoryListAPIView.as_view(),
        name="inventory-history",
    ),

    # POST /api/v1/inventory/adjust/
    path("adjust/", AdjustStockAPIView.as_view(), name="inventory-adjust"),
]
