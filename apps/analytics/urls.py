# apps/analytics/urls.py
from django.urls import path

from .views import (
    DailySalesSummaryListView,
    WarehouseKPIListView,
    RiderKPIListView,
    SKUAnalyticsDailyListView,
    InventorySnapshotDailyListView,
)

urlpatterns = [
    path("sales/daily/", DailySalesSummaryListView.as_view(), name="analytics-sales-daily"),
    path("warehouse/kpi/", WarehouseKPIListView.as_view(), name="analytics-warehouse-kpi"),
    path("riders/kpi/", RiderKPIListView.as_view(), name="analytics-rider-kpi"),
    path("sku/daily/", SKUAnalyticsDailyListView.as_view(), name="analytics-sku-daily"),
    path("inventory/daily/", InventorySnapshotDailyListView.as_view(), name="analytics-inventory-daily"),
]
