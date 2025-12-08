# apps/warehouse/views.py
import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError

from rest_framework import viewsets, views, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import (
    Warehouse, BinInventory, PickingTask, PickItem,
    PackingTask, GRN, CycleCountTask, ServiceArea
)
from .serializers import (
    WarehouseSerializer, BinInventorySerializer, PickingTaskSerializer,
    PackingTaskSerializer, DispatchRecordSerializer, ShortPickResolveSerializer,
    FulfillmentCancelSerializer, CreateGRNSerializer, GRNSerializer,
    PlacePutawaySerializer, PutawayTaskSerializer, CreateCycleCountSerializer,
    CycleCountTaskSerializer, RecordCycleCountSerializer, DispatchOTPVerifySerializer,
    ServiceAreaSerializer,
)
from .permissions import (
    PickerOnly, PackerOnly, WarehouseManagerOnly, AnyEmployee,
)
from .services import (
    scan_pick, mark_pickitem_skipped, complete_packing,
    resolve_skip_as_shortpick, admin_fulfillment_cancel,
    create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item, verify_dispatch_otp,
    check_service_availability, get_nearest_service_area,
)

logger = logging.getLogger(__name__)

# ... (Rest of the file remains exactly the same as your original, just the header fixed)
# To save space, I am not repeating the logic below as it was correct, only imports were wrong.
# Ensure you keep the classes WarehouseViewSet, etc.


# =========================================================
# WAREHOUSE STRUCTURE
# =========================================================

class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only list/detail of warehouses.
    Managers can later get write endpoints if needed.
    """
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]


class BinInventoryList(generics.ListAPIView):
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]
    serializer_class = BinInventorySerializer

    def get_queryset(self):
        qs = BinInventory.objects.select_related(
            "bin__zone__warehouse",
            "sku",
        )
        wh = self.request.query_params.get("warehouse")
        sku = self.request.query_params.get("sku")

        # limit to manager's warehouse if you store mapping
        emp = getattr(self.request.user, "employee_profile", None)
        if emp:
            qs = qs.filter(bin__zone__warehouse__code=emp.warehouse_code)

        if wh:
            qs = qs.filter(bin__zone__warehouse_id=wh)
        if sku:
            qs = qs.filter(sku_id=sku)

        return qs.order_by("bin__bin_code")

# =========================================================
# PICKING TASKS (PICKER APP)
# =========================================================

class PickingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Picker ke liye:
    - /api/v1/wms/picking/tasks/  -> mere assigned tasks
    """
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated, PickerOnly]

    def get_queryset(self):
        user = self.request.user
        return (
            PickingTask.objects
            .filter(picker=user)
            .select_related('warehouse', 'picker') # Foreign Keys
            .prefetch_related('items', 'items__sku', 'items__bin') # Reverse/Nested relations
            .order_by("-created_at")
        )

class ScanPickAPIView(views.APIView):
    """
    POST /api/v1/wms/picking/scan/
    body: { "task_id": "...", "pick_item_id": "...", "qty": 1 }
    """
    permission_classes = [IsAuthenticated, PickerOnly]

    def post(self, request):
        task_id = request.data.get("task_id")
        pick_item_id = request.data.get("pick_item_id")
        qty = request.data.get("qty", 1)

        if not (task_id and pick_item_id):
            return Response(
                {"detail": "task_id and pick_item_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                item = scan_pick(task_id, pick_item_id, qty, request.user)
        except Exception as e:
            logger.exception("scan_pick failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Scan recorded.",
                "pick_item_id": str(item.id),
                "picked_qty": item.picked_qty,
            },
            status=status.HTTP_200_OK,
        )


class MarkPickItemSkippedAPIView(views.APIView):
    """
    POST /api/v1/wms/picking/skip/
    body: { "task_id": "...", "pick_item_id": "...", "reason": "..." }
    """
    permission_classes = [IsAuthenticated, PickerOnly]

    def post(self, request):
        task_id = request.data.get("task_id")
        pick_item_id = request.data.get("pick_item_id")
        reason = request.data.get("reason") or ""

        if not (task_id and pick_item_id and reason):
            return Response(
                {"detail": "task_id, pick_item_id and reason required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                skip = mark_pickitem_skipped(
                    task_id,
                    pick_item_id,
                    request.user,
                    reason,
                    reopen_for_picker=False,
                )
        except Exception as e:
            logger.exception("mark_pickitem_skipped failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Item skipped.", "skip_id": str(skip.id)},
            status=status.HTTP_200_OK,
        )


# =========================================================
# PACKING (PACKER APP)
# =========================================================

class CompletePackingAPIView(views.APIView):
    """
    POST /api/v1/wms/packing/complete/
    body: { "packing_task_id": "..." }
    Returns DispatchRecord.
    """
    permission_classes = [IsAuthenticated, PackerOnly]

    def post(self, request):
        packing_task_id = request.data.get("packing_task_id")
        if not packing_task_id:
            return Response(
                {"detail": "packing_task_id required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                dispatch = complete_packing(packing_task_id, request.user)
        except Exception as e:
            logger.exception("complete_packing failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DispatchRecordSerializer(dispatch).data,
            status=status.HTTP_200_OK,
        )


# =========================================================
# DISPATCH OTP VERIFY (RIDER PICKUP)
# =========================================================

class DispatchOTPVerifyAPIView(views.APIView):
    """
    POST /api/v1/wms/dispatch/verify-otp/
    body: { "dispatch_id": "<uuid>", "otp": "1234" }
    """
    permission_classes = [IsAuthenticated, AnyEmployee]

    def post(self, request):
        serializer = DispatchOTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with transaction.atomic():
                dispatch = verify_dispatch_otp(
                    data["dispatch_id"],
                    data["otp"],
                    user=request.user,
                )
        except ValidationError as ve:
            # Django ValidationError -> DRF response
            return Response({"detail": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("verify_dispatch_otp failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "OTP verified. Order handed over to rider.",
                "dispatch": DispatchRecordSerializer(dispatch).data,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# MANAGER RESOLUTION (SHORT PICK / FC)
# =========================================================

class AdminResolveShortPickAPIView(views.APIView):
    """
    Manager resolves short-pick:
    POST /api/v1/wms/resolution/shortpick/
    body: { "skip_id": int, "note": "..." }
    """
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def post(self, request):
        serializer = ShortPickResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        skip_id = serializer.validated_data["skip_id"]
        note = serializer.validated_data["note"]

        from .models import PickSkip

        skip = get_object_or_404(PickSkip, id=skip_id)
        try:
            with transaction.atomic():
                spi = resolve_skip_as_shortpick(skip, request.user, note)
        except Exception as e:
            logger.exception("resolve_skip_as_shortpick failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Short-pick resolved.",
                "short_picked_qty": spi.short_picked_qty,
            },
            status=status.HTTP_200_OK,
        )


class AdminFulfillmentCancelAPIView(views.APIView):
    """
    Manager cancels remaining qty for a pick item:
    POST /api/v1/wms/resolution/fc/
    body: { "pick_item_id": int, "reason": "..." }
    """
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def post(self, request):
        serializer = FulfillmentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        pick_item_id = serializer.validated_data["pick_item_id"]
        reason = serializer.validated_data["reason"]

        pick_item = get_object_or_404(PickItem, id=pick_item_id)
        try:
            with transaction.atomic():
                fc_record = admin_fulfillment_cancel(
                    pick_item,
                    request.user,
                    reason,
                )
        except Exception as e:
            logger.exception("admin_fulfillment_cancel failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Fulfillment item cancelled.",
                "fc_id": str(fc_record.id),
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# INBOUND / PUTAWAY
# =========================================================

class CreateGRNAPIView(views.APIView):
    """
    Manager creates GRN + putaway task:
    POST /api/v1/wms/inbound/grn/
    """
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def post(self, request):
        serializer = CreateGRNSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        wh_id = serializer.validated_data["warehouse_id"]
        grn_number = serializer.validated_data["grn_number"]
        items = serializer.validated_data["items"]

        try:
            with transaction.atomic():
                grn, putaway_task = create_grn_and_putaway(
                    wh_id,
                    grn_number,
                    items,
                    created_by=request.user,
                )
        except Exception as e:
            logger.exception("create_grn_and_putaway failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        data = {
            "grn": GRNSerializer(grn).data,
            "putaway_task": PutawayTaskSerializer(putaway_task).data,
        }
        response = Response(data, status=status.HTTP_201_CREATED)
        # Idempotency middleware ke liye flag
        response["X-STORE-IDEMPOTENCY"] = "1"
        return response


class PlacePutawayItemView(views.APIView):
    """
    POST /api/v1/wms/inbound/putaway/place/
    """
    permission_classes = [IsAuthenticated, AnyEmployee]

    def post(self, request):
        serializer = PlacePutawaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        try:
            with transaction.atomic():
                item = place_putaway_item(
                    data["task_id"],
                    data["putaway_item_id"],
                    data["bin_id"],
                    data["qty_placed"],
                    request.user,
                )
        except Exception as e:
            logger.exception("place_putaway_item failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Putaway updated.", "item_id": str(item.id)},
            status=status.HTTP_200_OK,
        )


# =========================================================
# CYCLE COUNT
# =========================================================

class CycleCountTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Manager/Auditor can list CC tasks for their warehouses.
    Creation via separate API.
    """
    serializer_class = CycleCountTaskSerializer
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def get_queryset(self):
        # basic implementation: all tasks
        return CycleCountTaskSerializer.Meta.model.objects.all().order_by("-created_at")


class CreateCycleCountView(views.APIView):
    """
    POST /api/v1/wms/cycle-count/create/
    body: { "warehouse_id": int, "sample_bins": [int, ...] }
    """
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def post(self, request):
        serializer = CreateCycleCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        wh_id = serializer.validated_data["warehouse_id"]
        sample_bins = serializer.validated_data.get("sample_bins") or None

        try:
            with transaction.atomic():
                cc_task = create_cycle_count(wh_id, request.user, sample_bins)
        except Exception as e:
            logger.exception("create_cycle_count failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            CycleCountTaskSerializer(cc_task).data,
            status=status.HTTP_201_CREATED,
        )


class RecordCycleCountView(views.APIView):
    """
    POST /api/v1/wms/cycle-count/record/
    """
    permission_classes = [IsAuthenticated, WarehouseManagerOnly]

    def post(self, request):
        serializer = RecordCycleCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            with transaction.atomic():
                cc_item = record_cycle_count_item(
                    data["task_id"],
                    data["bin_id"],
                    data["sku_id"],
                    data["counted_qty"],
                    request.user,
                )
        except Exception as e:
            logger.exception("record_cycle_count_item failed: %s", e)
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "detail": "Cycle count recorded.",
                "cc_item_id": str(cc_item.id),
                "adjusted": cc_item.adjusted,
            },
            status=status.HTTP_200_OK,
        )


# =========================================================
# COMPATIBLE FUNCTION-STYLE VIEWS FOR urls.py
# =========================================================


# urls.py dynamic resolver names expect these:

scan_pick_view = ScanPickAPIView.as_view()
mark_pickitem_skipped_view = MarkPickItemSkippedAPIView.as_view()
complete_packing_view = CompletePackingAPIView.as_view()
place_putaway_item_view = PlacePutawayItemView.as_view()
record_cycle_count_view = RecordCycleCountView.as_view()
dispatch_otp_verify_view = DispatchOTPVerifyAPIView.as_view()


# =========================================================
# SERVICE AVAILABILITY & LOCATION-BASED CHECKS
# =========================================================

class CheckServiceAvailabilityAPIView(views.APIView):
    """
    Check if a customer location is serviceable.
    
    Query params or POST:
    - latitude (required)
    - longitude (required)
    - warehouse_id (optional)
    
    Response:
    {
        'is_available': bool,
        'warehouse': {...},
        'service_area': {...},
        'distance_km': float,
        'delivery_time_minutes': int,
        'message': str
    }
    """
    permission_classes = [AllowAny]  # Allow unauthenticated users to check service availability
    
    def get(self, request):
        """Handle GET request with query params"""
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        warehouse_id = request.query_params.get('warehouse_id')
        
        if not latitude or not longitude:
            return Response(
                {
                    'is_available': False,
                    'message': 'latitude and longitude are required',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            return Response(
                {
                    'is_available': False,
                    'message': 'latitude and longitude must be valid numbers',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = check_service_availability(latitude, longitude, warehouse_id)
        return Response(result, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Handle POST request with JSON body"""
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        warehouse_id = request.data.get('warehouse_id')
        
        if not latitude or not longitude:
            return Response(
                {
                    'is_available': False,
                    'message': 'latitude and longitude are required',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return Response(
                {
                    'is_available': False,
                    'message': 'latitude and longitude must be valid numbers',
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = check_service_availability(latitude, longitude, warehouse_id)
        return Response(result, status=status.HTTP_200_OK)


class GetNearestServiceAreaAPIView(views.APIView):
    """
    Get nearest service area to a location.
    Useful for showing "service coming soon to your area" messages.
    
    Query params or POST:
    - latitude (required)
    - longitude (required)
    
    Response:
    {
        'service_area': {
            'id': int,
            'name': str,
            'warehouse': str,
        },
        'distance_km': float
    }
    or null if no service area found.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Handle GET request"""
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            return Response(
                {'error': 'latitude and longitude must be valid numbers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_nearest_service_area(latitude, longitude)
        return Response(result, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Handle POST request"""
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (ValueError, TypeError):
            return Response(
                {'error': 'latitude and longitude must be valid numbers'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_nearest_service_area(latitude, longitude)
        return Response(result, status=status.HTTP_200_OK)


class ServiceAreaListAPIView(generics.ListAPIView):
    """
    List all active service areas.
    Can be used to display coverage zones on a map.
    """
    queryset = ServiceArea.objects.filter(is_active=True)
    serializer_class = ServiceAreaSerializer
    permission_classes = [AllowAny]