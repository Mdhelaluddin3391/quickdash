import logging
import math
from django.db import transaction, models
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D

from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.warehouse.models import Warehouse
from apps.accounts.permissions import IsRider
from .models import DeliveryTask, RiderEarning
from .serializers import (
    DeliveryTaskSerializer,
    RiderEarningSerializer,
    RiderProfileSerializer,
)

logger = logging.getLogger(__name__)

class DeliveryEstimateView(APIView):
    """
    Calculates ETA based on user location and nearest active warehouse.
    Logic: Base Prep Time (10-15m) + Travel Time (traffic factor).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response({"time": "...", "location": "Select Location"}, status=400)

        user_point = Point(float(lng), float(lat), srid=4326)
        
        # 1. Find Nearest Active Warehouse
        nearest_wh = Warehouse.objects.filter(is_active=True).annotate(
            distance=Distance('location', user_point)
        ).order_by('distance').first()

        if not nearest_wh:
            return Response({"time": "No Service", "location": "Out of Service Area"})

        # 2. Calculate Distance (in km)
        # Note: If SRID=4326, distance is in degrees. We convert approx or use project.
        # Assuming PostGIS logic (degrees):
        distance_km = nearest_wh.distance.km if hasattr(nearest_wh.distance, 'km') else nearest_wh.distance * 100
        
        # 3. Calculate Time (Heuristic)
        # Base Prep: 15 mins
        # Traffic Factor: 5 mins per km
        eta_minutes = 15 + math.ceil(distance_km * 5)
        
        return Response({
            "eta": f"{eta_minutes} mins",
            "distance_km": round(distance_km, 1),
            "serviceable": distance_km < 15.0 # 15km Radius check
        })

class RiderDashboardView(views.APIView):
    """
    Rider home screen:
    - GET: profile + state
    - POST: toggle On Duty / Off Duty
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        profile = request.user.rider_profile
        serializer = RiderProfileSerializer(profile)
        return Response(serializer.data)

    def post(self, request):
        profile = request.user.rider_profile

        if profile.on_duty:
            # going offline? ensure no active tasks
            active_task_exists = DeliveryTask.objects.filter(
                rider=profile,
                status__in=[
                    DeliveryTask.DeliveryStatus.ACCEPTED,
                    DeliveryTask.DeliveryStatus.AT_STORE,
                    DeliveryTask.DeliveryStatus.PICKED_UP,
                ],
            ).exists()
            if active_task_exists:
                return Response(
                    {"detail": "Cannot go offline with active deliveries."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        profile.on_duty = not profile.on_duty
        profile.save(update_fields=["on_duty"])
        return Response({"status": "updated", "on_duty": profile.on_duty})

class DeliveryTaskViewSet(viewsets.ModelViewSet):
    """
    Rider orders management.
    """
    serializer_class = DeliveryTaskSerializer
    permission_classes = [IsAuthenticated, IsRider]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return DeliveryTask.objects.filter(
            rider__user=self.request.user
        ).order_by("-created_at")

    def _ensure_owner(self, task: DeliveryTask, user):
        if not task.rider or task.rider.user != user:
            return False
        return True

    @action(detail=True, methods=["post"])
    def accept_order(self, request, pk=None):
        task = self.get_object()

        if not self._ensure_owner(task, request.user):
            return Response({"error": "Not your task."}, status=status.HTTP_403_FORBIDDEN)

        if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
            return Response({"error": "Order unavailable"}, status=status.HTTP_400_BAD_REQUEST)

        task.status = DeliveryTask.DeliveryStatus.ACCEPTED
        task.accepted_at = timezone.now()
        task.save()
        return Response({"status": "Order Accepted! Go to Store."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reach_store(self, request, pk=None):
        task = self.get_object()
        if not self._ensure_owner(task, request.user):
            return Response({"error": "Not your task."}, status=status.HTTP_403_FORBIDDEN)

        task.status = DeliveryTask.DeliveryStatus.AT_STORE
        task.save()
        return Response({"status": "Marked as at store."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def pickup_order(self, request, pk=None):
        task = self.get_object()
        if not self._ensure_owner(task, request.user):
            return Response({"error": "Not your task."}, status=status.HTTP_403_FORBIDDEN)

        task.status = DeliveryTask.DeliveryStatus.PICKED_UP
        task.picked_up_at = timezone.now()
        task.save()
        return Response({"status": "Order Picked Up! Go to Customer."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def complete_delivery(self, request, pk=None):
        task = self.get_object()
        if not self._ensure_owner(task, request.user):
            return Response({"error": "Not your task."}, status=status.HTTP_403_FORBIDDEN)

        # OTP Verification
        entered_otp = request.data.get("otp")
        if task.delivery_otp and task.delivery_otp != entered_otp:
            return Response({"error": "Invalid delivery OTP"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            task = DeliveryTask.objects.select_for_update().get(id=task.id)
            if task.status != DeliveryTask.DeliveryStatus.PICKED_UP:
                 return Response({"error": "Invalid State"}, status=409)

            task.status = DeliveryTask.DeliveryStatus.DELIVERED
            task.delivered_at = timezone.now()
            task.save()
            
        return Response({"status": "Order Delivered Successfully!"}, status=status.HTTP_200_OK)


class RiderEarningsView(views.APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        earnings_qs = RiderEarning.objects.filter(
            rider__user=request.user
        ).order_by("-created_at")

        serializer = RiderEarningSerializer(earnings_qs, many=True)
        today = timezone.now().date()
        
        total_today = earnings_qs.filter(created_at__date=today).aggregate(sum=models.Sum("total_earning")).get("sum") or 0
        total_unpaid = earnings_qs.filter(status=RiderEarning.EarningStatus.UNPAID).aggregate(sum=models.Sum("total_earning")).get("sum") or 0

        return Response({
            "history": serializer.data,
            "summary": {
                "today_total": total_today,
                "total_unpaid": total_unpaid,
            },
        })