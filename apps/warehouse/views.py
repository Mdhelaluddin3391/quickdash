from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PickingTask, PackingTask, DispatchRecord, Warehouse
from .serializers import (
    PickingTaskSerializer, PackingTaskSerializer, DispatchRecordSerializer,
    ScanPickSerializer
)
from .services import WarehouseOpsService
from .permissions import PickerOnly, PackerOnly

class PickingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated, PickerOnly]

    def get_queryset(self):
        return PickingTask.objects.filter(
            status__in=[PickingTask.Status.PENDING, PickingTask.Status.IN_PROGRESS]
        ).order_by('created_at')

class PackingTaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PackingTaskSerializer
    permission_classes = [IsAuthenticated, PackerOnly]

    def get_queryset(self):
        return PackingTask.objects.filter(
            status=PackingTask.Status.PENDING
        ).order_by('created_at')

class ScanPickView(views.APIView):
    permission_classes = [IsAuthenticated, PickerOnly]

    def post(self, request):
        serializer = ScanPickSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            WarehouseOpsService.scan_pick(
                task_id=serializer.validated_data['task_id'],
                pick_item_id=serializer.validated_data['pick_item_id'],
                qty=serializer.validated_data['quantity'],
                user=request.user
            )
            return Response({"status": "Scanned"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class CompletePackingView(views.APIView):
    permission_classes = [IsAuthenticated, PackerOnly]

    def post(self, request, pk):
        try:
            dispatch = WarehouseOpsService.complete_packing(pk, request.user)
            return Response(DispatchRecordSerializer(dispatch).data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)