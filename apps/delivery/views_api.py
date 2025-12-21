from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.gis.geos import Point
from django.utils import timezone
from apps.accounts.models import RiderProfile
import logging

logger = logging.getLogger(__name__)

class UpdateRiderLocationView(APIView):
    """
    Rider App calls this every 10-30 seconds.
    Updates the RiderProfile.current_location field (PostGIS Point).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.is_rider:
            return Response({"error": "Unauthorized"}, status=403)

        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response({"error": "Missing coordinates"}, status=400)

        try:
            rider_profile = user.rider_profile
            
            # Update Location
            point = Point(float(lng), float(lat), srid=4326)
            rider_profile.current_location = point
            rider_profile.last_location_update = timezone.now()
            rider_profile.save(update_fields=['current_location', 'last_location_update'])

            # Optional: If rider has an active task, log this point to a history table
            # for route playback later (Not implemented here for brevity)

            return Response({"status": "updated"})

        except RiderProfile.DoesNotExist:
            return Response({"error": "Rider profile not found"}, status=404)
        except Exception as e:
            logger.error(f"Location update failed: {e}")
            return Response({"error": "Server error"}, status=500)