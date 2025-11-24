# apps/inventory/views.py
import logging

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import (
    IsWarehouseManagerEmployee,
    IsEmployee,
)
from .models import InventoryStock, InventoryHistory
from .serializers import InventoryStockSerializer, InventoryHistorySerializer

logger = logging.getLogger(__name__)


class InventoryListAPIView(generics.ListAPIView):
    """
    Employees ke liye central inventory dekhne ki API.

    GET /api/v1/inventory/stock/?warehouse_id=...&sku_code=...&low_stock=true
    """
    permission_classes = [IsAuthenticated, IsEmployee]
    serializer_class = InventoryStockSerializer

    def get_queryset(self):
        qs = (
            InventoryStock.objects.select_related("sku", "warehouse")
            .all()
            .order_by("warehouse_id", "sku__sku_code")
        )

        warehouse_id = self.request.query_params.get("warehouse_id")
        sku_code = self.request.query_params.get("sku_code")
        low_stock = self.request.query_params.get("low_stock")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if sku_code:
            qs = qs.filter(sku__sku_code=sku_code)
        if low_stock == "true":
            qs = qs.filter(available_qty__lte=10)

        return qs


class InventoryHistoryListAPIView(generics.ListAPIView):
    """
    Audit trail for inventory changes.

    GET /api/v1/inventory/history/?warehouse_id=...&sku_id=...
    """
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]
    serializer_class = InventoryHistorySerializer

    def get_queryset(self):
        qs = (
            InventoryHistory.objects.select_related("warehouse", "sku", "stock")
            .all()
        )

        wh = self.request.query_params.get("warehouse_id")
        sku = self.request.query_params.get("sku_id")
        change_type = self.request.query_params.get("change_type")

        if wh:
            qs = qs.filter(warehouse_id=wh)
        if sku:
            qs = qs.filter(sku_id=sku)
        if change_type:
            qs = qs.filter(change_type=change_type)

        return qs.order_by("-created_at")[:500]


class AdjustStockAPIView(APIView):
    """
    EMERGENCY ONLY – Manual adjustment of central inventory.

    WARNING:
    - Ye BIN-level (Warehouse app) ko touch nahi karta
    - Sirf InventoryStock + InventoryHistory ko update karega
    - Iska use sirf investigation / mismatch patching ke waqt karna chahiye
      jab tumne physical audit already kar liya ho.

    POST /api/v1/inventory/adjust/
    body: { "sku_id": "...", "warehouse_id": "...", "quantity": +10/-5 }

    Microservice rule still respected:
    - Normal flows hammesha WMS movement + signal se aane chahiye,
      yeh sirf override hai.
    """
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]

    def post(self, request):
        sku_id = request.data.get("sku_id")
        warehouse_id = request.data.get("warehouse_id")
        quantity = request.data.get("quantity")

        if not all([sku_id, warehouse_id, quantity]):
            return Response(
                {
                    "detail": "sku_id, warehouse_id, and quantity required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            qty_delta = int(quantity)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid quantity provided for inventory adjustment: %s",
                quantity,
            )
            return Response(
                {"detail": "Quantity must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            stock, created = InventoryStock.objects.select_for_update().get_or_create(
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                defaults={"available_qty": 0, "reserved_qty": 0},
            )

            new_available = stock.available_qty + qty_delta
            if new_available < 0:
                return Response(
                    {"detail": "Stock cannot be negative."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            stock.available_qty = new_available
            stock.save()

            InventoryHistory.objects.create(
                stock=stock,
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                delta_available=qty_delta,
                delta_reserved=0,
                available_after=stock.available_qty,
                reserved_after=stock.reserved_qty,
                change_type="manual_adjustment",
                reference="MANUAL_UI",
            )

            return Response(
                {
                    "message": "Stock adjusted successfully",
                    "new_available_qty": stock.available_qty,
                },
                status=status.HTTP_200_OK,
            )

        except Exception:
            logger.exception(
                "Unexpected error adjusting stock for SKU %s in WH %s",
                sku_id,
                warehouse_id,
            )
            return Response(
                {"detail": "Internal server error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
