# apps/warehouse/views.py

from rest_framework import viewsets, generics, status
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from apps.accounts.permissions import IsPickerEmployee, IsPackerEmployee, IsWarehouseManagerEmployee, IsAdminEmployee
from .models import (
    Warehouse, PickingTask, BinInventory, PutawayTask, CycleCountTask,
    PickSkip, PickItem
)
from .serializers import (
    WarehouseSerializer, PickingTaskSerializer, BinInventorySerializer, DispatchRecordSerializer,
    CreateGRNSerializer, CreateCycleCountSerializer,
    PlacePutawayItemSerializer, RecordCycleCountSerializer, CycleCountTaskSerializer,
    MarkPickItemSkippedSerializer, ResolveShortPickSerializer, FulfillmentCancelSerializer,
    PutawayItemPlacedSerializer
)
from .services import (
    scan_pick, complete_packing, 
    create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item,
    mark_pickitem_skipped, resolve_skip_as_shortpick, admin_fulfillment_cancel
)
from .exceptions import WarehouseAutomationError
import logging
logger = logging.getLogger(__name__)

# --- ViewSets ---

class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

class BinInventoryList(generics.ListAPIView):
    serializer_class = BinInventorySerializer
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]
    def get_queryset(self):
        qs = BinInventory.objects.select_related('bin__shelf__aisle__zone__warehouse', 'sku')
        if self.request.query_params.get('bin_id'):
            qs = qs.filter(bin_id=self.request.query_params.get('bin_id'))
        return qs

class PickingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickingTask.objects.all().prefetch_related('items')
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated, IsPickerEmployee]
    
    def get_queryset(self):
        return PickingTask.objects.exclude(status='completed').order_by('created_at')

class CycleCountTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CycleCountTask.objects.all().select_related('warehouse').order_by('-created_at')
    serializer_class = CycleCountTaskSerializer
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsWarehouseManagerEmployee])
    def create_task(self, request):
        serializer = CreateCycleCountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            task = create_cycle_count(data['warehouse_id'], request.user, data.get('sample_bins'))
            return Response(self.get_serializer(task).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# --- Picking Workflow (Picker/Packer) ---

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPickerEmployee])
def scan_pick_view(request):
    required_fields = ['task_id', 'pick_item_id']
    if not all(request.data.get(f) for f in required_fields):
         return Response({"detail": f"Missing required fields: {', '.join(required_fields)}"}, status=400)
         
    try:
        item = scan_pick(
            request.data['task_id'], 
            request.data['pick_item_id'], 
            int(request.data.get('qty', 1)), 
            request.user
        )
        return Response({"status": "item_scanned", "picked_qty": item.picked_qty})
    except WarehouseAutomationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception("Error during scan_pick")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPackerEmployee])
def complete_packing_view(request):
    try:
        packing_task_id = request.data.get('packing_task_id')
        if not packing_task_id:
            return Response({"detail": "packing_task_id required."}, status=status.HTTP_400_BAD_REQUEST)

        dispatch = complete_packing(packing_task_id, request.user)
        return Response(DispatchRecordSerializer(dispatch).data)
    except Exception as e:
        logger.exception("Error during complete_packing")
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# --- Inbound/Putaway Views (Manager/Picker) ---

class CreateGRNAPIView(APIView):
    """Admin/Manager: Creates a GRN and corresponding Putaway Task."""
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]
    
    def post(self, request):
        serializer = CreateGRNSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            grn, putaway_task = create_grn_and_putaway(
                data['warehouse_id'], 
                data['grn_number'], 
                data['items'], 
                request.user
            )
            return Response({
                "grn_id": grn.id, 
                "putaway_task_id": putaway_task.id,
                "detail": "GRN created and Putaway task generated."
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPickerEmployee]) # Picker/Putaway user
def place_putaway_item_view(request):
    """Picker/Putaway User: Records an item being placed into a bin."""
    serializer = PlacePutawayItemSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        placed_item = place_putaway_item(
            data['task_id'],
            data['putaway_item_id'],
            data['bin_id'],
            data['qty_placed'],
            request.user
        )
        return Response({
            "status": "placed",
            "item_details": PutawayItemPlacedSerializer(placed_item).data
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# --- Picking Resolution Views (Manager/Admin) ---

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPickerEmployee])
def mark_pickitem_skipped_view(request):
    """Picker marks an item as skipped (e.g., item not found)."""
    serializer = MarkPickItemSkippedSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    
    try:
        skip = mark_pickitem_skipped(
            data['task_id'],
            data['pick_item_id'],
            request.user,
            data['reason'],
            data.get('reopen_for_picker', False)
        )
        return Response({"status": "skipped", "skip_id": skip.id})
    except WarehouseAutomationError as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AdminResolveShortPickAPIView(APIView):
    """Manager/Admin: Resolves a skip by short-picking the item."""
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]

    def post(self, request):
        serializer = ResolveShortPickSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        try:
            skip = get_object_or_404(PickSkip, id=data['skip_id'])
            spi = resolve_skip_as_shortpick(skip, request.user, data.get('notes', ''))
            return Response({"status": "short_pick_resolved", "incident_id": spi.id})
        except WarehouseAutomationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AdminFulfillmentCancelAPIView(APIView):
    """Admin: Cancels an unpicked item from the order and triggers refund."""
    permission_classes = [IsAuthenticated, IsAdminEmployee]

    def post(self, request):
        serializer = FulfillmentCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            pick_item = get_object_or_404(PickItem, id=data['pick_item_id'])
            fc_record = admin_fulfillment_cancel(pick_item, request.user, data['reason'])
            return Response({"status": "fulfillment_cancel_processed", "fc_id": fc_record.id, "refund_initiated": fc_record.refund_initiated})
        except WarehouseAutomationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# --- Cycle Count Views ---

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPickerEmployee]) # Or dedicated Auditor role
def record_cycle_count_view(request):
    """Picker/Auditor records the counted quantity for a bin/sku pair."""
    serializer = RecordCycleCountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    
    try:
        cc_item = record_cycle_count_item(
            data['task_id'],
            data['bin_id'],
            data['sku_id'],
            data['counted_qty'],
            request.user
        )
        return Response({
            "status": "count_recorded", 
            "adjusted": cc_item.adjusted,
            "expected_qty": cc_item.expected_qty,
            "counted_qty": cc_item.counted_qty,
        })
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)