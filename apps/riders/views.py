from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import RiderProfile
from .serializers import RiderProfileSerializer
from .services import RiderService

class RiderProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = RiderService.get_profile(request.user)
        return Response(RiderProfileSerializer(profile).data)

class RiderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Toggle Online/Offline status
        """
        new_status = request.data.get('status')
        profile = RiderService.toggle_status(request.user, new_status)
        return Response({
            "status": "success",
            "current_status": profile.current_status
        })

class RiderLocationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        
        if not lat or not lng:
            return Response({"error": "Missing coordinates"}, status=status.HTTP_400_BAD_REQUEST)
            
        RiderService.update_location(request.user, lat, lng)
        return Response({"status": "updated"})