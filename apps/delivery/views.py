# apps/delivery/views.py
from django.db import transaction, models
from django.utils import timezone

from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from apps.warehouse.models import Warehouse
import math
from apps.accounts.permissions import IsRider
from .models import DeliveryTask, RiderEarning
from .serializers import (
    DeliveryTaskSerializer,
    RiderEarningSerializer,
    RiderProfileSerializer,
)


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


class DeliveryTaskViewSet(viewsets.ModelViewSet):
    """
    Rider ke orders manage karne ke liye APIs.

    /api/v1/delivery/tasks/               -> list (my tasks)
    /api/v1/delivery/tasks/<id>/accept/   -> accept order
    /api/v1/delivery/tasks/<id>/pickup/   -> pickup confirm
    /api/v1/delivery/tasks/<id>/complete/ -> complete delivery
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
            return Response(
                {"error": "Not your task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
            return Response(
                {"error": "Order already accepted or unavailable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = DeliveryTask.DeliveryStatus.ACCEPTED
        task.accepted_at = timezone.now()
        task.save()
        return Response(
            {"status": "Order Accepted! Go to Store."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reach_store(self, request, pk=None):
        """
        Optional intermediate step: Rider AT_STORE.
        """
        task = self.get_object()

        if not self._ensure_owner(task, request.user):
            return Response(
                {"error": "Not your task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if task.status not in [
            DeliveryTask.DeliveryStatus.ACCEPTED,
            DeliveryTask.DeliveryStatus.AT_STORE,
        ]:
            return Response(
                {"error": "Invalid state transition."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = DeliveryTask.DeliveryStatus.AT_STORE
        task.save()
        return Response(
            {"status": "Marked as at store."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def pickup_order(self, request, pk=None):
        task = self.get_object()

        if not self._ensure_owner(task, request.user):
            return Response(
                {"error": "Not your task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if task.status not in [
            DeliveryTask.DeliveryStatus.ACCEPTED,
            DeliveryTask.DeliveryStatus.AT_STORE,
        ]:
            return Response(
                {"error": "Cannot pickup in current status."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Pickup OTP check (optional, you can enable later)
        # otp = request.data.get("otp")
        # if task.pickup_otp and otp != task.pickup_otp:
        #     return Response({"error": "Invalid pickup OTP"}, status=400)

        task.status = DeliveryTask.DeliveryStatus.PICKED_UP
        task.picked_up_at = timezone.now()
        task.save()
        return Response(
            {"status": "Order Picked Up! Go to Customer."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def complete_delivery(self, request, pk=None):
        task = self.get_object()

        if not self._ensure_owner(task, request.user):
            return Response(
                {"error": "Not your task."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if task.status != DeliveryTask.DeliveryStatus.PICKED_UP:
            return Response(
                {"error": "Only picked-up orders can be completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entered_otp = request.data.get("otp")
        if task.delivery_otp and task.delivery_otp != entered_otp:
            return Response(
                {"error": "Invalid delivery OTP"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            task.status = DeliveryTask.DeliveryStatus.DELIVERED
            task.delivered_at = timezone.now()
            task.save()  # model save will: update order, rider, earning, signal

        return Response(
            {
                "status": "Order Delivered Successfully! Money added to wallet."
            },
            status=status.HTTP_200_OK,
        )


class RiderEarningsView(views.APIView):
    """
    Rider earnings history.

    GET /api/v1/delivery/earnings/
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        earnings_qs = RiderEarning.objects.filter(
            rider__user=request.user
        ).order_by("-created_at")

        serializer = RiderEarningSerializer(earnings_qs, many=True)

        today = timezone.now().date()
        total_today = (
            earnings_qs.filter(created_at__date=today)
            .aggregate(sum=models.Sum("total_earning"))
            .get("sum")
            or 0
        )

        return Response(
            {
                "history": serializer.data,
                "summary": {
                    "today_total": total_today,
                    "total_unpaid": earnings_qs.filter(
                        status=RiderEarning.EarningStatus.UNPAID
                    )
                    .aggregate(sum=models.Sum("total_earning"))
                    .get("sum")
                    or 0,
                },
            }
        )






class DeliveryEstimateView(APIView):
    """
    Calculates ETA based on user location and nearest active warehouse.
    Logic: Base Prep Time (10m) + Travel Time (3m per km).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response({"time": "...", "location": "Select Location"}, status=400)

        user_point = Point(float(lng), float(lat), srid=4326)
        
        # 1. Find Nearest Warehouse
        nearest_wh = Warehouse.objects.filter(is_active=True).annotate(
            distance=Distance('location', user_point)
        ).order_by('distance').first()

        if not nearest_wh:
            return Response({"time": "No Service", "location": "Out of Service Area"})

        # 2. Calculate Distance (in km)
        distance_km = nearest_wh.distance.km
        
        # 3. Calculate Time (Simple Heuristic)
        # Base Prep: 10 mins + Travel: 4 mins per km
        eta_minutes = 10 + math.ceil(distance_km * 4)
        
        # Cap min time at 15 mins
        if eta_minutes < 15: eta_minutes = 15

        # 4. Reverse Geocode (Optional, or just send ETA)
        # For now, we return the ETA. Frontend can handle the City name via Google Maps API or Browser API.
        
        return Response({
            "eta": f"{eta_minutes} mins",
            "distance_km": round(distance_km, 1),
            "serviceable": distance_km < 15.0 # 15km Radius check
        })