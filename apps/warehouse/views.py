from rest_framework import viewsets, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404

# Apps Imports
from apps.accounts.permissions import IsStoreStaff # Ensure this exists or use IsAuthenticated
from .models import PickingTask, PickItem
from .serializers import PickingTaskSerializer

class PickerTaskViewSet(viewsets.ModelViewSet):
    """
    Picker ke liye APIs:
    1. GET /api/warehouse/tasks/ -> Mere assigned tasks dikhao
    2. POST /api/warehouse/tasks/{id}/complete_pick/ -> Task complete karo
    """
    serializer_class = PickingTaskSerializer
    permission_classes = [IsAuthenticated] # Add IsStoreStaff if available

    def get_queryset(self):
        # Sirf wahi tasks dikhao jo is user (picker) ko assigned hain
        user = self.request.user
        return PickingTask.objects.filter(picker=user).order_by('-created_at')

class ScanItemView(views.APIView):
    """
    API: POST /api/warehouse/scan-item/
    Picker jab barcode scan karega toh yeh API call hogi.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_id = request.data.get('task_id')
        sku_code = request.data.get('sku_code') # Barcode scan se aaya hua
        location_code = request.data.get('location_code') # Optional validation

        try:
            with transaction.atomic():
                # 1. Item dhoondo jo pending hai
                pick_item = PickItem.objects.select_for_update().filter(
                    task_id=task_id,
                    sku__sku_code=sku_code,
                    picked_qty__lt=models.F('qty_to_pick')
                ).first()

                if not pick_item:
                    return Response({"error": "Wrong item scanned or item already picked!"}, status=400)

                # 2. Pick Confirm karo
                pick_item.picked_qty += 1
                pick_item.save()

                # 3. Check karo agar poora task complete ho gaya
                task = pick_item.task
                remaining_items = task.items.filter(picked_qty__lt=models.F('qty_to_pick')).exists()
                
                if not remaining_items:
                    task.status = PickingTask.TaskStatus.COMPLETED
                    task.completed_at = timezone.now()
                    task.save()
                    return Response({"message": "Item Scanned. TASK COMPLETED! 🚀"})

                return Response({"message": "Item Scanned Successfully."})

        except Exception as e:
            return Response({"error": str(e)}, status=400)