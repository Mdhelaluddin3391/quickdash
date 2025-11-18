from rest_framework import viewsets, generics, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsPickerEmployee, IsPackerEmployee, IsWarehouseManagerEmployee
from .models import Warehouse, PickingTask, BinInventory
from .serializers import WarehouseSerializer, PickingTaskSerializer, BinInventorySerializer, DispatchRecordSerializer
from .services import scan_pick, complete_packing

# --- ViewSets ---

class WarehouseViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Warehouse.objects.filter(is_active=True)
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated]

class BinInventoryList(generics.ListAPIView):
    serializer_class = BinInventorySerializer
    permission_classes = [IsAuthenticated, IsWarehouseManagerEmployee]
    def get_queryset(self):
        qs = BinInventory.objects.select_related('bin', 'sku')
        if self.request.query_params.get('bin_id'):
            qs = qs.filter(bin_id=self.request.query_params.get('bin_id'))
        return qs

class PickingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PickingTask.objects.all().prefetch_related('items')
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated, IsPickerEmployee]
    
    def get_queryset(self):
        # Sirf pending/in_progress tasks dikhao
        return PickingTask.objects.exclude(status='completed').order_by('created_at')

# --- Function Based Views for Ops ---

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPickerEmployee])
def scan_pick_view(request):
    try:
        scan_pick(
            request.data['task_id'], 
            request.data['pick_item_id'], 
            request.data.get('qty', 1), 
            request.user
        )
        return Response({"status": "item_scanned"})
    except Exception as e:
        return Response({"detail": str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsPackerEmployee])
def complete_packing_view(request):
    try:
        dispatch = complete_packing(request.data['packing_task_id'], request.user)
        return Response(DispatchRecordSerializer(dispatch).data)
    except Exception as e:
        return Response({"detail": str(e)}, status=400)