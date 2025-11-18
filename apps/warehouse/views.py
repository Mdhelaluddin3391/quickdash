import logging

from django.db.models import F
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import (
    IsPickerEmployee,
    IsPackerEmployee,
    IsAuditorEmployee,
    IsWarehouseManagerEmployee,
    IsAdminEmployee,
)

from apps.inventory.models import BinInventory, InventoryStock
from apps.warehouse.models import (
    Warehouse, Bin,
    PickingTask, PickItem,
    PackingTask, DispatchRecord,
)
from apps.warehouse.serializers import (
    WarehouseSerializer, BinSerializer,
    BinInventorySerializer, InventoryStockSerializer,
    PickingTaskSerializer, PickItemSerializer,
    PackingTaskSerializer, DispatchRecordSerializer,
    GRNSerializer, PutawayTaskSerializer, PutawayItemSerializer,
    CycleCountTaskSerializer, CycleCountItemSerializer,
)
from apps.warehouse.permissions import IsWarehouseManagerOrReadOnly
from apps.warehouse.services import (
    reserve_stock_for_order, OutOfStockError,
    scan_pick, create_packing_task_from_picking, complete_packing,
    create_pick_skip, record_short_pick, create_fulfillment_cancel,
    create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item,
)
from apps.warehouse.tasks import orchestrate_order_fulfilment_from_order_payload

logger = logging.getLogger(__name__)


# ===================================================================
#                          WAREHOUSE STRUCTURE
# ===================================================================

class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, IsWarehouseManagerOrReadOnly]


class BinViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bin.objects.all().select_related("shelf__aisle__zone__warehouse")
    serializer_class = BinSerializer
    permission_classes = [IsAuthenticated]


# ===================================================================
#                          WMS TASK VIEWSETS
# ===================================================================

class PickingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickingTask.objects.all().prefetch_related("items", "warehouse")
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        task = self.get_object()
        if task.status == "pending":
            task.status = "in_progress"
            task.started_at = task.started_at or task.created_at
            task.save(update_fields=["status", "started_at"])
        return Response(PickingTaskSerializer(task).data)


class PackingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PackingTask.objects.all().prefetch_related("items", "picking_task__warehouse")
    serializer_class = PackingTaskSerializer
    permission_classes = [IsAuthenticated]


class DispatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DispatchRecord.objects.all().select_related("warehouse", "packing_task")
    serializer_class = DispatchRecordSerializer
    permission_classes = [IsAuthenticated]


# ===================================================================
#                           INVENTORY LISTING
# ===================================================================

class BinInventoryList(generics.ListAPIView):
    serializer_class = BinInventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = BinInventory.objects.select_related("bin", "sku")
        bin_id = self.request.query_params.get("bin_id")
        sku_id = self.request.query_params.get("sku_id")
        if bin_id:
            qs = qs.filter(bin_id=bin_id)
        if sku_id:
            qs = qs.filter(sku_id=sku_id)
        return qs


class InventoryStockList(generics.ListAPIView):
    serializer_class = InventoryStockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = InventoryStock.objects.select_related("warehouse", "sku")
        wh_id = self.request.query_params.get("warehouse_id")
        sku_id = self.request.query_params.get("sku_id")
        if wh_id:
            qs = qs.filter(warehouse_id=wh_id)
        if sku_id:
            qs = qs.filter(sku_id=sku_id)
        return qs


# ===================================================================
#                        ORDER WEBHOOK (SYNC+ASYNC)
# ===================================================================

class OrderWebhookAPIView(APIView):
    """
    Payload:
    {
      "order_id": "O123",
      "warehouse_id": "<uuid>",
      "items": [{"sku_id": "<uuid>", "qty": 2}],
      "mode": "async" or "sync"
    }
    """
    permission_classes = [IsWarehouseManagerEmployee]

    def post(self, request, *args, **kwargs):
        data = request.data
        order_id = data.get("order_id")
        items = data.get("items", [])
        warehouse_id = data.get("warehouse_id")
        mode = data.get("mode", "async")

        if not order_id or not items:
            return Response({"detail": "order_id and items required"}, status=400)

        payload = {
            "order_id": order_id,
            "items": items,
            "warehouse_id": warehouse_id,
        }

        # Case 1: Async Mode
        if mode == "async":
            orchestrate_order_fulfilment_from_order_payload.delay(payload)
            # Async response ke liye bhi idempotency enable kar sakte hain
            response = Response({"status": "queued"}, status=202)
            response['X-STORE-IDEMPOTENCY'] = '1'
            return response

        if warehouse_id is None:
            return Response({"detail": "warehouse_id required for sync mode"}, status=400)

        # Case 2: Sync Mode
        try:
            allocations = reserve_stock_for_order(order_id, warehouse_id, items)
            # Import inside method to avoid circular import if necessary, 
            # though top-level is usually fine if structure allows.
            from apps.warehouse.services import create_picking_task_from_reservation
            task = create_picking_task_from_reservation(order_id, warehouse_id, allocations)
        except OutOfStockError as e:
            return Response({"detail": str(e)}, status=400)

        # --- FIX START: Idempotency Header Setup ---
        # Pehle direct return kar rahe the, ab variable mein lekar header add karenge
        response = Response(PickingTaskSerializer(task).data, status=201)
        response['X-STORE-IDEMPOTENCY'] = '1'
        return response
        # --- FIX END ---

# ===================================================================
#                              PICKING (PICKER ONLY)
# ===================================================================

@api_view(["POST"])
@permission_classes([IsPickerEmployee])
def scan_pick_view(request):
    try:
        item = scan_pick(
            request.data["task_id"],
            request.data["bin_id"],
            request.data["sku_id"],
            request.data.get("qty", 1),
            request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    return Response(PickItemSerializer(item).data)


@api_view(["POST"])
@permission_classes([IsPickerEmployee])
def pick_skip_view(request):
    try:
        skip = create_pick_skip(
            request.data["pick_item_id"],
            request.user,
            request.data.get("reason", ""),
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    from .serializers import PickSkipSerializer
    return Response(PickSkipSerializer(skip).data)


@api_view(["POST"])
@permission_classes([IsPickerEmployee])
def short_pick_view(request):
    try:
        incident = record_short_pick(
            request.data["pick_item_id"],
            request.user,
            request.data.get("note", ""),
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    from .serializers import ShortPickIncidentSerializer
    return Response(ShortPickIncidentSerializer(incident).data)


# ===================================================================
#                     ADMIN OVERRIDE (ADMIN ONLY)
# ===================================================================

@api_view(["POST"])
@permission_classes([IsAdminEmployee])
def admin_fc_view(request):
    try:
        fc = create_fulfillment_cancel(
            request.data["pick_item_id"],
            request.user,
            request.data.get("reason", ""),
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    from .serializers import FulfillmentCancelSerializer
    return Response(FulfillmentCancelSerializer(fc).data)


# ===================================================================
#                              PACKING (PACKER ONLY)
# ===================================================================

@api_view(["POST"])
@permission_classes([IsPackerEmployee])
def create_packing_view(request):
    try:
        pack_task = create_packing_task_from_picking(
            request.data["picking_task_id"],
            request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    return Response(PackingTaskSerializer(pack_task).data)


@api_view(["POST"])
@permission_classes([IsPackerEmployee])
def complete_packing_view(request):
    try:
        dispatch = complete_packing(
            request.data["packing_task_id"],
            request.user,
            request.data.get("total_weight_kg"),
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

    return Response(DispatchRecordSerializer(dispatch).data)


# ===================================================================
#                     INBOUND (GRN + PUTAWAY – MANAGER ONLY)
# ===================================================================

@api_view(["POST"])
@permission_classes([IsWarehouseManagerEmployee])
def create_grn_putaway_view(request):
    wh_id = request.data.get("warehouse_id")
    grn_no = request.data.get("grn_no")
    items = request.data.get("items", [])

    if not wh_id or not grn_no or not items:
        return Response({"detail": "warehouse_id, grn_no, items required"}, status=400)

    try:
        grn, task = create_grn_and_putaway(
            wh_id, grn_no, items, created_by=request.user
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

    return Response(
        {
            "grn": GRNSerializer(grn).data,
            "putaway_task": PutawayTaskSerializer(task).data,
        },
        status=201,
    )


@api_view(["POST"])
@permission_classes([IsWarehouseManagerEmployee])
def place_putaway_item_view(request):
    try:
        item = place_putaway_item(
            request.data["task_id"],
            request.data["bin_id"],
            request.data["sku_id"],
            request.data["qty"],
            request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

    return Response(PutawayItemSerializer(item).data)


# ===================================================================
#                       CYCLE COUNT (AUDITOR ONLY)
# ===================================================================

@api_view(["POST"])
@permission_classes([IsAuditorEmployee])
def create_cycle_view(request):
    wh_id = request.data.get("warehouse_id")
    bin_ids = request.data.get("bin_ids")
    try:
        task = create_cycle_count(wh_id, request.user, sample_bins=bin_ids)
    except Exception as e:
        return Response({"detail": str(e)}, status=400)
    return Response(CycleCountTaskSerializer(task).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuditorEmployee])
def record_cycle_item_view(request):
    try:
        item = record_cycle_count_item(
            request.data["task_id"],
            request.data["bin_id"],
            request.data["sku_id"],
            request.data["counted_qty"],
            request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

    return Response(CycleCountItemSerializer(item).data)
