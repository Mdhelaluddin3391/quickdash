from django.utils import timezone
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction  # <-- FIX: Import kiya

from apps.accounts.permissions import IsRider
from apps.accounts.models import RiderProfile
from apps.orders.models import OrderTimeline  # <-- FIX: Import kiya
from .models import RiderLocation, DeliveryTask
from .serializers import (
    UpdateRiderLocationSerializer,
    RiderLocationSerializer,
    RiderDeliveryTaskSerializer,
)

import logging
logger = logging.getLogger(__name__)

# ===================================================================
#                      RIDER LOCATION VIEWS
# ===================================================================

class UpdateRiderLocationAPIView(APIView):
    """
    Rider App is API ko har 10-30 seconds mein call karega.
    POST /api/v1/delivery/location/update/
    """
    permission_classes = [IsAuthenticated, IsRider]

    def post(self, request, *args, **kwargs):
        rider_profile = request.user.rider_profile
        
        serializer = UpdateRiderLocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        
        # RiderLocation model mein update ya create karein
        location, created = RiderLocation.objects.update_or_create(
            rider=rider_profile,
            defaults={
                'lat': data['lat'],
                'lng': data['lng'],
                'on_duty': data['on_duty'],
            }
        )
        
        # RiderProfile par bhi 'on_duty' status update karein
        if rider_profile.on_duty != data['on_duty']:
            rider_profile.on_duty = data['on_duty']
            rider_profile.save(update_fields=['on_duty'])
            
        return Response(
            {"status": "location_updated", "on_duty": location.on_duty},
            status=status.HTTP_200_OK
        )


class GetRiderLocationAPIView(generics.RetrieveAPIView):
    """
    (Optional) Admin ya internal service ke liye rider ki location dekhne hetu.
    GET /api/v1/delivery/location/<rider_id>/
    """
    permission_classes = [IsAuthenticated] # Isko IsAdmin se protect kar sakte hain
    serializer_class = RiderLocationSerializer
    queryset = RiderLocation.objects.all()
    lookup_field = 'rider__id'


# ===================================================================
#                      RIDER TASK MANAGEMENT VIEWS
# ===================================================================

class GetMyCurrentTaskAPIView(APIView):
    """
    Rider App yeh call karke apna current active task fetch karega.
    GET /api/v1/delivery/task/current/
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request, *args, **kwargs):
        rider_profile = request.user.rider_profile
        
        # Rider ka active task dhoondein (jo delivered ya failed na ho)
        active_task = DeliveryTask.objects.filter(
            rider=rider_profile
        ).exclude(
            status__in=['delivered', 'failed']
        ).select_related(
            # FIX: 'dispatch_record__warehouse' ko 'order__warehouse' se badla
            'order__warehouse' 
        ).first() # Ek rider ke paas ek hi active task hoga

        if not active_task:
            return Response(
                {"detail": "No active delivery task found."},
                status=status.HTTP_204_NO_CONTENT
            )
            
        serializer = RiderDeliveryTaskSerializer(active_task)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UpdateTaskStatusAPIView(APIView):
    """
    Rider App isko call karke task ka status update karega.
    POST /api/v1/delivery/task/update_status/
    Body: {"task_id": "...", "status": "...", "otp": "..." (optional)}
    """
    permission_classes = [IsAuthenticated, IsRider]

    def post(self, request, *args, **kwargs):
        task_id = request.data.get('task_id')
        new_status = request.data.get('status')
        otp = request.data.get('otp')
        
        if not task_id or not new_status:
            return Response(
                {"detail": "task_id and status are required."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # FIX: Humein 'order' ko bhi fetch karna hai taaki use update kar sakein
            task = get_object_or_404(
                DeliveryTask.objects.select_related('order'), 
                id=task_id, 
                rider=request.user.rider_profile
            )
        except DeliveryTask.DoesNotExist:
            return Response({"detail": "Task not found or not assigned to you."}, status=status.HTTP_404_NOT_FOUND)

        # Basic Status transition logic
        current_status = task.status
        
        if new_status == "at_warehouse":
            if current_status != "assigned":
                return Response({"detail": f"Cannot move from {current_status} to at_warehouse."}, status=status.HTTP_400_BAD_REQUEST)
            task.status = "at_warehouse"
        
        elif new_status == "picked_up":
            if current_status != "at_warehouse":
                return Response({"detail": "Must be 'at_warehouse' to 'pick_up'."}, status=status.HTTP_400_BAD_REQUEST)
            # Pickup OTP check karein
            if task.pickup_otp != otp:
                return Response({"detail": "Invalid Pickup OTP."}, status=status.HTTP_400_BAD_REQUEST)
            task.status = "picked_up"
            task.picked_up_at = timezone.now()
        
        elif new_status == "at_customer":
            if current_status != "picked_up":
                return Response({"detail": "Must be 'picked_up' to 'at_customer'."}, status=status.HTTP_400_BAD_REQUEST)
            task.status = "at_customer"

        elif new_status == "delivered":
            if current_status != "at_customer":
                return Response({"detail": "Must be 'at_customer' to 'deliver'."}, status=status.HTTP_400_BAD_REQUEST)
            # Delivery OTP check karein
            if task.delivery_otp != otp:
                return Response({"detail": "Invalid Delivery OTP."}, status=status.HTTP_400_BAD_REQUEST)
            
            # FIX: Ek saath 3 models update karne ke liye transaction ka istemaal
            with transaction.atomic():
                task.status = "delivered"
                task.delivered_at = timezone.now()
                
                # FIX: Order ka status bhi 'delivered' set karein
                if task.order:
                    task.order.status = "delivered"
                    task.order.delivered_at = task.delivered_at
                    task.order.save(update_fields=['status', 'delivered_at'])

                    # FIX: Order timeline mein bhi add karein
                    OrderTimeline.objects.create(
                        order=task.order,
                        status="delivered",
                        notes=f"Delivered by rider {request.user.rider_profile.rider_code}."
                    )
                
                task.save() # Task ko aakhir mein save karein

        else:
            return Response({"detail": f"Invalid target status: {new_status}"}, status=status.HTTP_400_BAD_REQUEST)

        # Status change (at_warehouse, picked_up, at_customer) ke liye
        if not new_status == "delivered":
             task.save()
        
        # Customer ko update hue task ki detail waapas bhejein
        serializer = RiderDeliveryTaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)