from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .services import RiderService
from .serializers import RiderProfileSerializer, UpdateLocationSerializer, UpdateStatusSerializer
from apps.accounts.permissions import IsRider

class RiderProfileView(APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        profile = RiderService.get_profile(request.user)
        serializer = RiderProfileSerializer(profile)
        return Response(serializer.data)

class RiderStatusView(APIView):
    """
    Rider toggles their availability (ON_DUTY / OFF_DUTY).
    """
    permission_classes = [IsAuthenticated, IsRider]

    def post(self, request):
        serializer = UpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_status = serializer.validated_data['status']
        profile = RiderService.toggle_status(request.user, new_status)
        
        return Response({
            "status": "success",
            "current_status": profile.current_status
        })

class RiderLocationView(APIView):
    """
    Heartbeat endpoint for rider location updates.
    """
    permission_classes = [IsAuthenticated, IsRider]

    def post(self, request):
        serializer = UpdateLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        RiderService.update_location(
            request.user, 
            lat=serializer.validated_data['lat'],
            lng=serializer.validated_data['lng']
        )
        return Response({"status": "updated"}, status=status.HTTP_200_OK)