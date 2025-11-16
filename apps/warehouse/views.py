import logging
from django.db.models import F
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser

from apps.warehouse.models import (
    Warehouse, Bin, PickingTask, PickItem,
    PackingTask, DispatchRecord, PickSkip
)
from apps.warehouse.serializers import (
    WarehouseSerializer, BinSerializer, BinInventorySerializer, InventoryStockSerializer,
    PickingTaskSerializer, PickItemSerializer, PackingTaskSerializer,
    DispatchRecordSerializer, GRNSerializer, PutawayTaskSerializer,
    PutawayItemSerializer, CycleCountItemSerializer
)
from apps.inventory.models import BinInventory, InventoryStock, SKU
from apps.warehouse.permissions import IsWarehouseManagerOrReadOnly
from apps.warehouse.services import (
    reserve_stock_for_order, OutOfStockError,
    assign_picker, scan_pick, create_picking_task_from_reservation,
    create_packing_task_from_picking, complete_packing, assign_dispatch,
    mark_picked_up, mark_delivered, admin_fulfillment_cancel,
    create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item
)

from apps.warehouse.tasks import orchestrate_order_fulfilment_from_order_payload

logger = logging.getLogger(__name__)



class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, IsWarehouseManagerOrReadOnly]


class BinViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Bin.objects.all().select_related('shelf__aisle__zone__warehouse')
    serializer_class = BinSerializer
    permission_classes = [IsAuthenticated]


class BinInventoryList(generics.ListAPIView):
    serializer_class = BinInventorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        sku = self.request.query_params.get('sku')
        warehouse = self.request.query_params.get('warehouse')

        qs = BinInventory.objects.select_related('bin', 'sku')
        if sku:
            qs = qs.filter(sku__sku_code=sku) | qs.filter(sku_id=sku)
        if warehouse:
            qs = qs.filter(bin__shelf__aisle__zone__warehouse__id=warehouse)

        return qs.order_by('-qty')



class ReserveStockAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, warehouse_id):
        """
        body: { "order_id": "xxxx", "items": [{"sku_id": "xxx", "qty": 2}] }
        """
        payload = request.data
        order_id = payload.get('order_id')
        items = payload.get('items', [])

        # convert sku_code to sku.id if needed
        for it in items:
            sid = it.get("sku_id")
            if isinstance(sid, str):
                sku = SKU.objects.filter(sku_code=sid).first()
                if sku:
                    it["sku_id"] = sku.id

        try:
            allocations = reserve_stock_for_order(order_id, warehouse_id, items)
        except OutOfStockError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        resp = Response({"allocations": allocations}, status=status.HTTP_200_OK)
        resp["X-STORE-IDEMPOTENCY"] = "1"
        return resp



class PickingTaskViewSet(viewsets.ModelViewSet):
    queryset = PickingTask.objects.all().select_related(
        "warehouse", "picker"
    ).prefetch_related("items__sku", "items__bin")
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        user = request.user
        task = assign_picker(pk, user)
        return Response(PickingTaskSerializer(task).data)

    @action(detail=True, methods=["get"])
    def picklist(self, request, pk=None):
        task = self.get_object()
        items = task.items.select_related("sku", "bin").all()

        reopen, normal = [], []
        for it in items:
            skip = getattr(it, "skip", None)
            if skip and skip.reopen_after_scan and not skip.resolved:
                reopen.append(it)
            else:
                normal.append(it)

        ordered = reopen + normal
        skipped_present = PickSkip.objects.filter(
            pick_item__task=task, resolved=False
        ).exists()

        serializer = PickItemSerializer(ordered, many=True)
        return Response(
            {
                "pick_items": serializer.data,
                "skipped_items_present": skipped_present,
            }
        )


class PickScanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        body: { task_id, pick_item_id, bin_code, sku_code, qty }
        """
        payload = request.data
        try:
            pi, extra = scan_pick(
                payload["task_id"],
                payload["pick_item_id"],
                payload["bin_code"],
                payload["sku_code"],
                int(payload["qty"]),
                request.user,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = PickItemSerializer(pi).data
        data.update(extra)

        resp = Response(data)
        resp["X-STORE-IDEMPOTENCY"] = "1"
        return resp




@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pick_skip_view(request):
    task_id = request.data.get("task_id")
    pick_item_id = request.data.get("pick_item_id")
    reason = request.data.get("reason", "")

    try:
        skip = mark_pickitem_skipped(task_id, pick_item_id, request.user, reason)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response(
        {
            "skip_id": str(skip.id),
            "pick_item_id": pick_item_id,
            "reopen_after_scan": skip.reopen_after_scan,
        }
    )
    resp["X-STORE-IDEMPOTENCY"] = "1"
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pick_unscan_view(request):
    """
    Undo scan
    """
    from apps.warehouse.models import PickItem

    task_id = request.data.get("task_id")
    pick_item_id = request.data.get("pick_item_id")
    qty = int(request.data.get("qty", 1))

    try:
        pi = PickItem.objects.select_for_update().get(
            pk=pick_item_id, task_id=task_id
        )
        if pi.picked_qty < qty:
            raise ValueError("cannot unpick more than picked")

        # reverse physical inventory
        bi = BinInventory.objects.select_for_update().get(
            bin_id=pi.bin_id, sku_id=pi.sku_id
        )
        bi.qty = F("qty") + qty
        bi.reserved_qty = F("reserved_qty") + qty
        bi.save(update_fields=["qty", "reserved_qty"])

        inv = InventoryStock.objects.select_for_update().get(
            warehouse_id=pi.task.warehouse_id, sku_id=pi.sku_id
        )
        inv.reserved_qty = F("reserved_qty") + qty
        inv.save(update_fields=["reserved_qty"])

        pi.picked_qty = F("picked_qty") - qty
        pi.save(update_fields=["picked_qty"])

    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response({"pick_item_id": pick_item_id, "picked_qty": pi.picked_qty})
    resp["X-STORE-IDEMPOTENCY"] = "1"
    return resp


@api_view(["POST"])
@permission_classes([IsAdminUser])
def admin_fc_view(request):
    pick_item_id = request.data.get("pick_item_id")
    reason = request.data.get("reason", "")

    try:
        pi = PickItem.objects.get(pk=pick_item_id)
        fc = admin_fulfillment_cancel(pi, request.user, reason=reason)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response({"fc_id": str(fc.id), "pick_item_id": pick_item_id})
    resp["X-STORE-IDEMPOTENCY"] = "1"
    return resp



class PackingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PackingTask.objects.all().select_related(
        "picking_task", "packer"
    ).prefetch_related("items__sku")
    serializer_class = PackingTaskSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def create_from_picking(self, request, pk=None):
        try:
            pack = create_packing_task_from_picking(pk)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PackingTaskSerializer(pack).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        label = request.data.get("package_label")
        try:
            pack, dr = complete_packing(pk, request.user, package_label=label)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "packing": PackingTaskSerializer(pack).data,
                "dispatch": DispatchRecordSerializer(dr).data,
            }
        )



class DispatchViewSet(viewsets.ModelViewSet):
    queryset = DispatchRecord.objects.all().select_related(
        "packing_task", "packing_task__picking_task"
    )
    serializer_class = DispatchRecordSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        try:
            dr = assign_dispatch(
                pk,
                request.data.get("courier"),
                request.data.get("courier_id"),
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(DispatchRecordSerializer(dr).data)

    @action(detail=True, methods=["post"])
    def picked_up(self, request, pk=None):
        try:
            dr = mark_picked_up(pk)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DispatchRecordSerializer(dr).data)

    @action(detail=True, methods=["post"])
    def delivered(self, request, pk=None):
        try:
            dr = mark_delivered(pk)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(DispatchRecordSerializer(dr).data)



class OrderWebhookAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data
        order_id = payload.get("order_id")
        items = payload.get("items", [])

        # resolve sku codes
        for it in items:
            sid = it.get("sku_id")
            if isinstance(sid, str):
                sku = SKU.objects.filter(sku_code=sid).first()
                if sku:
                    it["sku_id"] = str(sku.id)

        if not order_id or not items:
            return Response(
                {"detail": "order_id and items required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        orchestrate_order_fulfilment_from_order_payload.delay(
            {"order_id": str(order_id), "items": items, "metadata": payload.get("metadata", {})}
        )

        resp = Response({"status": "enqueued"}, status=status.HTTP_202_ACCEPTED)
        resp["X-STORE-IDEMPOTENCY"] = "1"
        return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_grn_putaway_view(request):
    wh_id = request.data.get("warehouse_id")
    grn_no = request.data.get("grn_no")
    items = request.data.get("items", [])

    try:
        grn, task = create_grn_and_putaway(
            wh_id, grn_no, items, created_by=request.user
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response(
        {"grn": GRNSerializer(grn).data, "putaway_task": PutawayTaskSerializer(task).data}
    )
    resp["X-STORE-IDEMPOTENCY"] = "1"
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def place_putaway_item_view(request):
    try:
        pai = place_putaway_item(
            request.data["putaway_task_id"],
            request.data["putaway_item_id"], request.data["bin_id"],
            int(request.data["qty"]), request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    resp = Response(PutawayItemSerializer(pai).data)
    resp["X-STORE-IDEMPOTENCY"] = "1"
    return resp


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_cycle_view(request):
    wh_id = request.data.get("warehouse_id")
    bins = request.data.get("sample_bins")
    task = create_cycle_count(wh_id, request.user, sample_bins=bins)
    return Response({"task_id": str(task.id)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def record_cycle_item_view(request):
    try:
        item = record_cycle_count_item(
            request.data["task_id"],
            request.data["bin_id"],
            request.data["sku_id"],
            int(request.data["counted_qty"]),
            request.user,
        )
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(CycleCountItemSerializer(item).data)
