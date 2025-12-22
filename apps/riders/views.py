from rest_framework import viewsets, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from .models import RiderProfile, RiderEarnings
from .serializers import RiderProfileSerializer, RiderEarningsSerializer, LocationUpdateSerializer
from .services import RiderService

class RiderProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Rider manages their own profile.
    """
    serializer_class = RiderProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RiderProfile.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def status(self, request):
        """
        Toggle Online/Offline
        """
        is_online = request.data.get('is_online', False)
        profile = RiderService.toggle_status(request.user, is_online)
        return Response(RiderProfileSerializer(profile).data)

    @action(detail=False, methods=['post'])
    def location(self, request):
        """
        Heartbeat location update
        """
        serializer = LocationUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        RiderService.update_location(
            request.user, 
            lat=serializer.validated_data['lat'],
            lng=serializer.validated_data['lng']
        )
        return Response({"status": "Updated"}, status=status.HTTP_200_OK)

class RiderEarningsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RiderEarningsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if not hasattr(self.request.user, 'rider_profile'):
            return RiderEarnings.objects.none()
        return RiderEarnings.objects.filter(rider=self.request.user).order_by('-created_at')