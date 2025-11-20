from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction

# Permissions (Niche Step 8 mein banayenge)
from apps.accounts.permissions import IsRider 
from .models import DeliveryTask, RiderEarning
from .serializers import DeliveryTaskSerializer, RiderEarningSerializer, RiderProfileSerializer

class RiderDashboardView(views.APIView):
    """
    Rider ka Home Screen API.
    Status (Online/Offline) toggle karne aur Profile dekhne ke liye.
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        profile = request.user.rider_profile
        serializer = RiderProfileSerializer(profile)
        return Response(serializer.data)

    def post(self, request):
        # Toggle Online/Offline
        profile = request.user.rider_profile
        profile.is_online = not profile.is_online
        profile.save()
        return Response({"status": "Online" if profile.is_online else "Offline"})

class DeliveryTaskViewSet(viewsets.ModelViewSet):
    """
    Rider ke Orders manage karne ke liye APIs.
    """
    serializer_class = DeliveryTaskSerializer
    permission_classes = [IsAuthenticated, IsRider]
    http_method_names = ['get', 'post', 'patch']

    def get_queryset(self):
        # Sirf is rider ke tasks dikhao
        return DeliveryTask.objects.filter(rider__user=self.request.user).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def accept_order(self, request, pk=None):
        task = self.get_object()
        if task.status != DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT:
            return Response({"error": "Order already accepted or unavailable"}, status=400)
        
        task.status = DeliveryTask.DeliveryStatus.ACCEPTED
        task.accepted_at = timezone.now()
        task.save()
        return Response({"status": "Order Accepted! Go to Store."})

    @action(detail=True, methods=['post'])
    def pickup_order(self, request, pk=None):
        task = self.get_object()
        # OTP Verification Logic (Optional)
        # if task.pickup_otp != request.data.get('otp'):
        #     return Response({"error": "Invalid Pickup OTP"}, status=400)

        task.status = DeliveryTask.DeliveryStatus.PICKED_UP
        task.picked_up_at = timezone.now()
        task.save()
        return Response({"status": "Order Picked Up! Go to Customer."})

    @action(detail=True, methods=['post'])
    def complete_delivery(self, request, pk=None):
        task = self.get_object()
        # Delivery OTP Verification
        entered_otp = request.data.get('otp')
        if task.delivery_otp and task.delivery_otp != entered_otp:
            return Response({"error": "Invalid Delivery OTP"}, status=400)

        with transaction.atomic():
            task.status = DeliveryTask.DeliveryStatus.DELIVERED
            task.delivered_at = timezone.now()
            task.save()
            # Earning logic model ke save() method mein handle ho jayegi
            
        return Response({"status": "Order Delivered Successfully! Money added to wallet."})

class RiderEarningsView(views.APIView):
    """
    Rider apni kamai ki history dekh sake.
    """
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        earnings = RiderEarning.objects.filter(rider__user=request.user).order_by('-created_at')
        serializer = RiderEarningSerializer(earnings, many=True)
        
        total_today = 0 # Yahan calculation logic laga sakte hain
        return Response({
            "history": serializer.data,
            "summary": "Total earned logic goes here"
        })