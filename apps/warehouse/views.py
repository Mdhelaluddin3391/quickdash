import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.conf import settings

from rest_framework import viewsets, views, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.warehouse.utils.warehouse_selector import WarehouseSelector, get_nearest_service_area
from .models import (
    Warehouse, Bin, BinInventory, PickingTask, PickItem,
    PackingTask, GRN, PutawayTask, CycleCountTask, ServiceArea, PickSkip
)
from .serializers import (
    WarehouseSerializer, BinSerializer, BinInventorySerializer, 
    PickingTaskSerializer, PackingTaskSerializer, DispatchRecordSerializer, 
    ShortPickResolveSerializer, FulfillmentCancelSerializer, CreateGRNSerializer, 
    GRNSerializer, PlacePutawaySerializer, PutawayTaskSerializer, 
    CreateCycleCountSerializer, CycleCountTaskSerializer, RecordCycleCountSerializer, 
    DispatchOTPVerifySerializer, ServiceAreaSerializer,
)
from .permissions import (
    PickerOnly, PackerOnly, WarehouseManagerOnly, AnyEmployee,
)
from .services import (
    scan_pick, mark_pickitem_skipped, complete_packing,
    resolve_skip_as_shortpick, admin_fulfillment_cancel,
    create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item, verify_dispatch_otp,
    check_service_availability,
)

logger = logging.getLogger(__name__)

# ==========================
# CORE VIEWSETS
# ==========================

class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

class BinViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View for Warehouse Managers to audit/view bins.
    """
    serializer_class = BinSerializer
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def get_queryset(self):
        qs = Bin.objects.select_related("zone__warehouse")
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(zone__warehouse__code=emp.warehouse_code)
        
        warehouse_id = self.request.query_params.get("warehouse_id")
        if warehouse_id:
            qs = qs.filter(zone__warehouse_id=warehouse_id)
            
        return qs

class BinInventoryList(generics.ListAPIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    serializer_class = BinInventorySerializer

    def get_queryset(self):
        qs = BinInventory.objects.select_related("bin__zone__warehouse", "sku")
        wh = self.request.query_params.get("warehouse")
        sku = self.request.query_params.get("sku")
        
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(bin__zone__warehouse__code=emp.warehouse_code)

        if wh: qs = qs.filter(bin__zone__warehouse_id=wh)
        if sku: qs = qs.filter(sku_id=sku)

        return qs.order_by("bin__bin_code")

# ==========================
# TASK VIEWSETS
# ==========================

class PickingTaskViewSet(viewsets.ModelViewSet):
    # Old: queryset = PickingTask.objects.all()
    # Fix: Fetch related items and the SKU details in one go
    queryset = PickingTask.objects.select_related('order', 'picker').prefetch_related(
        'items__sku', 
        'items__bin'
    ).all()
    serializer_class = PickingTaskSerializer

class PackingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Allows Packers to see tasks that need packing.
    """
    serializer_class = PackingTaskSerializer
    permission_classes = [IsAuthenticated, PackerOnly]

    def get_queryset(self):
        qs = PackingTask.objects.select_related(
            'picking_task', 
            'picking_task__warehouse',
            'picking_task__picker', 
            'packer'
        ).prefetch_related('picking_task__items', 'picking_task__items__sku')

        # Filter by employee warehouse if applicable
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(picking_task__warehouse__code=emp.warehouse_code)

        # Allow filtering by status (default to open tasks)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
            
        return qs.order_by("-created_at")

class PutawayTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Allows warehouse staff to view Putaway tasks generated from GRNs.
    """
    serializer_class = PutawayTaskSerializer
    permission_classes = [IsAuthenticated, AnyEmployee]

    def get_queryset(self):
        qs = PutawayTask.objects.select_related('grn', 'warehouse', 'putaway_user')\
            .prefetch_related('items', 'items__grn_item__sku', 'items__placed_bin')
        
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(warehouse__code=emp.warehouse_code)
            
        return qs.order_by("-created_at")

class CycleCountTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CycleCountTaskSerializer
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    
    def get_queryset(self):
        qs = CycleCountTask.objects.select_related('warehouse', 'task_user')
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(warehouse__code=emp.warehouse_code)
        return qs.order_by("-created_at")

class GRNViewSet(viewsets.ReadOnlyModelViewSet):
    """
    View for Warehouse Managers to see Inbound history.
    """
    serializer_class = GRNSerializer
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def get_queryset(self):
        qs = GRN.objects.select_related('warehouse', 'created_by')\
            .prefetch_related('items', 'items__sku')
        
        emp = getattr(self.request.user, "employee_profile", None)
        if emp and emp.warehouse_code:
            qs = qs.filter(warehouse__code=emp.warehouse_code)
            
        return qs.order_by("-created_at")

# ==========================
# OPERATIONAL APIS
# ==========================

class ScanPickAPIView(views.APIView):
    permission_classes = [IsAuthenticated, PickerOnly]
    def post(self, request):
        task_id = request.data.get("task_id")
        pick_item_id = request.data.get("pick_item_id")
        qty = request.data.get("qty", 1)

        if not (task_id and pick_item_id):
            return Response({"detail": "task_id and pick_item_id required."}, status=400)

        try:
            with transaction.atomic():
                item = scan_pick(task_id, pick_item_id, qty, request.user)
        except Exception as e:
            logger.exception("scan_pick failed: %s", e)
            return Response({"detail": str(e)}, status=400)

        return Response({"detail": "Scan recorded.", "pick_item_id": str(item.id), "picked_qty": item.picked_qty}, status=200)

class MarkPickItemSkippedAPIView(views.APIView):
    permission_classes = [IsAuthenticated, PickerOnly]
    def post(self, request):
        task_id = request.data.get("task_id")
        pick_item_id = request.data.get("pick_item_id")
        reason = request.data.get("reason") or ""

        try:
            with transaction.atomic():
                skip = mark_pickitem_skipped(task_id, pick_item_id, request.user, reason, reopen_for_picker=False)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        return Response({"detail": "Item skipped.", "skip_id": str(skip.id)}, status=200)

class CompletePackingAPIView(views.APIView):
    permission_classes = [IsAuthenticated, PackerOnly]
    def post(self, request):
        packing_task_id = request.data.get("packing_task_id")
        try:
            with transaction.atomic():
                dispatch = complete_packing(packing_task_id, request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(DispatchRecordSerializer(dispatch).data, status=200)

class DispatchOTPVerifyAPIView(views.APIView):
    permission_classes = [IsAuthenticated, AnyEmployee]
    def post(self, request):
        serializer = DispatchOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                dispatch = verify_dispatch_otp(data["dispatch_id"], data["otp"], user=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "OTP verified.", "dispatch": DispatchRecordSerializer(dispatch).data}, status=200)

class AdminResolveShortPickAPIView(views.APIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    def post(self, request):
        serializer = ShortPickResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        skip = get_object_or_404(PickSkip, id=serializer.validated_data["skip_id"])
        try:
            with transaction.atomic():
                spi = resolve_skip_as_shortpick(skip, request.user, serializer.validated_data["note"])
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "Resolved.", "short_picked_qty": spi.short_picked_qty}, status=200)

class AdminFulfillmentCancelAPIView(views.APIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    def post(self, request):
        serializer = FulfillmentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pick_item = get_object_or_404(PickItem, id=serializer.validated_data["pick_item_id"])
        try:
            with transaction.atomic():
                fc = admin_fulfillment_cancel(pick_item, request.user, serializer.validated_data["reason"])
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "Cancelled.", "fc_id": str(fc.id)}, status=200)

class CreateGRNAPIView(views.APIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    def post(self, request):
        serializer = CreateGRNSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                grn, task = create_grn_and_putaway(
                    serializer.validated_data["warehouse_id"],
                    serializer.validated_data["grn_number"],
                    serializer.validated_data["items"],
                    created_by=request.user
                )
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({
            "grn": GRNSerializer(grn).data,
            "putaway_task": PutawayTaskSerializer(task).data
        }, status=201)

class PlacePutawayItemView(views.APIView):
    permission_classes = [IsAuthenticated, AnyEmployee]
    def post(self, request):
        serializer = PlacePutawaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            with transaction.atomic():
                item = place_putaway_item(d["task_id"], d["putaway_item_id"], d["bin_id"], d["qty_placed"], request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "Putaway updated.", "item_id": str(item.id)}, status=200)

class CreateCycleCountView(views.APIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    def post(self, request):
        serializer = CreateCycleCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                task = create_cycle_count(serializer.validated_data["warehouse_id"], request.user, serializer.validated_data.get("sample_bins"))
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response(CycleCountTaskSerializer(task).data, status=201)

class RecordCycleCountView(views.APIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    def post(self, request):
        serializer = RecordCycleCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            with transaction.atomic():
                item = record_cycle_count_item(d["task_id"], d["bin_id"], d["sku_id"], d["counted_qty"], request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"detail": "Recorded.", "cc_item_id": str(item.id)}, status=200)

# =========================================================
# SERVICE AVAILABILITY & LOCATION
# =========================================================

SERVICE_WAREHOUSE_KEY = 'quickdash_service_warehouse_id'

class CheckServiceabilityAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response(
                {"serviceable": False, "message": "Location coordinates missing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        warehouse = WarehouseSelector.get_serviceable_warehouse(lat, lng)

        if warehouse:
            request.session[SERVICE_WAREHOUSE_KEY] = warehouse.id
            request.session.modified = True 
            
            return Response({
                "serviceable": True,
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "message": f"Delivering from {warehouse.name}"
            })

        else:
            if SERVICE_WAREHOUSE_KEY in request.session:
                del request.session[SERVICE_WAREHOUSE_KEY]
            
            return Response({
                "serviceable": False,
                "message": "Sorry, we do not deliver to this area yet."
            })

class GetNearestServiceAreaAPIView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        if not lat or not lng:
             return Response({'error': "Latitude and Longitude required"}, status=status.HTTP_400_BAD_REQUEST)
             
        result = get_nearest_service_area(lat, lng)
        return Response(result, status=status.HTTP_200_OK)

class ServiceAreaListAPIView(generics.ListAPIView):
    queryset = ServiceArea.objects.filter(is_active=True)
    serializer_class = ServiceAreaSerializer
    permission_classes = [AllowAny]

# View Instances for URLs
scan_pick_view = ScanPickAPIView.as_view()
mark_pickitem_skipped_view = MarkPickItemSkippedAPIView.as_view()
complete_packing_view = CompletePackingAPIView.as_view()
place_putaway_item_view = PlacePutawayItemView.as_view()
record_cycle_count_view = RecordCycleCountView.as_view()
dispatch_otp_verify_view = DispatchOTPVerifyAPIView.as_view()