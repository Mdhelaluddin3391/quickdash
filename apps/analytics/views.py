# apps/analytics/views.py
from rest_framework import generics, permissions

from .models import (
    DailySalesSummary,
    WarehouseKPISnapshot,
    RiderKPISnapshot,
    SKUAnalyticsDaily,
    InventorySnapshotDaily,
)
from .serializers import (
    DailySalesSummarySerializer,
    WarehouseKPISnapshotSerializer,
    RiderKPISnapshotSerializer,
    SKUAnalyticsDailySerializer,
    InventorySnapshotDailySerializer,
)


class IsStaffUser(permissions.BasePermission):
    """
    Only staff/admin can access analytics APIs.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class DailySalesSummaryListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    serializer_class = DailySalesSummarySerializer

    def get_queryset(self):
        qs = DailySalesSummary.objects.all().order_by("-date")
        days = self.request.query_params.get("days")
        if days:
            try:
                limit = int(days)
                qs = qs[:limit]
            except ValueError:
                pass
        return qs


class WarehouseKPIListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    serializer_class = WarehouseKPISnapshotSerializer

    def get_queryset(self):
        qs = WarehouseKPISnapshot.objects.select_related("warehouse").order_by(
            "-date", "warehouse__code"
        )
        warehouse_id = self.request.query_params.get("warehouse_id")
        date_str = self.request.query_params.get("date")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if date_str:
            qs = qs.filter(date=date_str)
        return qs


class RiderKPIListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    serializer_class = RiderKPISnapshotSerializer

    def get_queryset(self):
        qs = RiderKPISnapshot.objects.select_related("rider", "rider__user").order_by(
            "-date"
        )
        rider_id = self.request.query_params.get("rider_id")
        date_str = self.request.query_params.get("date")

        if rider_id:
            qs = qs.filter(rider_id=rider_id)
        if date_str:
            qs = qs.filter(date=date_str)
        return qs


class SKUAnalyticsDailyListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    serializer_class = SKUAnalyticsDailySerializer

    def get_queryset(self):
        qs = SKUAnalyticsDaily.objects.select_related("sku").order_by("-date", "sku__name")
        sku_id = self.request.query_params.get("sku_id")
        date_str = self.request.query_params.get("date")

        if sku_id:
            qs = qs.filter(sku_id=sku_id)
        if date_str:
            qs = qs.filter(date=date_str)
        return qs


class InventorySnapshotDailyListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated, IsStaffUser]
    serializer_class = InventorySnapshotDailySerializer

    def get_queryset(self):
        qs = InventorySnapshotDaily.objects.select_related(
            "warehouse", "sku"
        ).order_by("-date", "warehouse__code")
        warehouse_id = self.request.query_params.get("warehouse_id")
        sku_id = self.request.query_params.get("sku_id")
        date_str = self.request.query_params.get("date")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if sku_id:
            qs = qs.filter(sku_id=sku_id)
        if date_str:
            qs = qs.filter(date=date_str)
        return qs
