# apps/delivery/views.py

from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.db.models import Sum

# Permissions
from apps.accounts.permissions import IsRider

# Models & Serializers
from .models import DeliveryTask, RiderEarning
from .serializers import DeliveryTaskSerializer, OTPVerificationSerializer
from apps.riders.serializers import RiderProfileSerializer

# Services
from .services import DeliveryService
from apps.riders.services import RiderService

class DeliveryTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Rider API for managing deliveries.
    """
    serializer_class = DeliveryTaskSerializer
    permission_classes = [IsAuthenticated, IsRider]

    def get_queryset(self):
        # Only show tasks assigned to the logged-in rider
        return DeliveryTask.objects.filter(rider__user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        try:
            DeliveryService.rider_accept_task(pk, request.user)
            return Response({"status": "Accepted"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def pickup(self, request, pk=None):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            DeliveryService.process_pickup(pk, request.user, serializer.validated_data['otp'])
            return Response({"status": "Picked Up"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            DeliveryService.complete_delivery(pk, request.user, serializer.validated_data['otp'])
            return Response({"status": "Delivered"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RiderDashboardView(views.APIView):
    """
    Aggregates Rider Status, Active Task, and Today's metrics.
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        rider_profile = RiderService.get_profile(request.user)
        
        # 1. Get Active Task (if any)
        active_task = DeliveryTask.objects.filter(
            rider=rider_profile,
            status__in=[
                DeliveryTask.DeliveryStatus.ASSIGNED,
                DeliveryTask.DeliveryStatus.ACCEPTED,
                DeliveryTask.DeliveryStatus.AT_STORE,
                DeliveryTask.DeliveryStatus.PICKED_UP
            ]
        ).first()

        # 2. Calculate Today's Earnings
        today = timezone.now().date()
        todays_earnings = RiderEarning.objects.filter(
            rider=rider_profile,
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0.00

        data = {
            "profile": RiderProfileSerializer(rider_profile).data,
            "active_task": DeliveryTaskSerializer(active_task).data if active_task else None,
            "metrics": {
                "todays_earnings": todays_earnings,
                # Add other metrics like "completed_trips" here via Analytics service if needed
            }
        }
        return Response(data)


class RiderEarningsView(generics.ListAPIView):
    """
    History of Rider Earnings.
    """
    permission_classes = [IsAuthenticated, IsRider]
    # We can create a specific serializer for earnings if needed, 
    # but for now we'll use a simple construction or a new serializer.
    # To keep it simple without adding files, we use a basic Value/Dict response or generic serializer.
    # Assuming RiderEarningSerializer exists or using generic values.
    
    def get(self, request):
        rider_profile = RiderService.get_profile(request.user)
        earnings = RiderEarning.objects.filter(rider=rider_profile).order_by('-created_at')
        
        data = [
            {
                "id": str(e.id),
                "amount": e.amount,
                "date": e.created_at,
                "order_ref": e.delivery_task.order.order_id if e.delivery_task else "N/A"
            }
            for e in earnings
        ]
        return Response(data)


class DeliveryEstimateView(views.APIView):
    """
    Public Endpoint to estimate delivery fee and time.
    Used by Checkout page.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # In a real scenario, this calculates distance between Warehouse and Customer Lat/Lng
        # For V1, we return standard configuration.
        from django.conf import settings
        
        return Response({
            "fee": getattr(settings, 'BASE_DELIVERY_FEE', 20.00),
            "eta_minutes": 30, # Could be dynamic based on load
            "serviceable": True # Assuming middleware already checked location
        })