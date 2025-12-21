from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.contrib.gis.geos import Point
from apps.warehouse.services import LocationService
from apps.accounts.models import Address

class CheckServiceabilityView(APIView):
    """
    Public endpoint to check if we deliver to a specific lat/lng.
    Does NOT require login (needed for landing page).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if not lat or not lng:
            return Response(
                {"error": "Latitude and Longitude are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Warehouse service logic call
        is_serviceable, warehouse, area, dist = LocationService.get_serviceable_warehouse(lat, lng)

        if is_serviceable:
            eta = LocationService.calculate_eta(dist)
            # Save to session so we don't ask again immediately
            request.session['serviceable_lat'] = lat
            request.session['serviceable_lng'] = lng
            request.session['warehouse_id'] = warehouse.id
            
            return Response({
                "serviceable": True,
                "warehouse": {
                    "id": warehouse.id,
                    "name": warehouse.name
                },
                "eta_minutes": eta,
                "message": f"Delivery in {eta} mins"
            })
        else:
            return Response({
                "serviceable": False,
                "message": "Sorry, we do not deliver to this location yet."
            })

class SaveCurrentLocationView(APIView):
    """
    Saves the user's current GPS location as a temporary 'Current Location' address
    or updates their default address.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        address_text = request.data.get('address_text', 'Current Location')
        pincode = request.data.get('pincode', '')
        
        if not lat or not lng:
            return Response({"error": "Missing coordinates"}, status=400)

        # Create Point object (Longitude, Latitude)
        location_point = Point(float(lng), float(lat), srid=4326)

        # Update or Create Address
        address, created = Address.objects.update_or_create(
            user=request.user,
            address_type=Address.AddressType.OTHER, 
            defaults={
                'location': location_point,
                'full_address': address_text,
                'city': 'Detected',
                'pincode': pincode,
                'is_default': True # Mark as active/default for this session
            }
        )

        return Response({"status": "success", "address_id": address.id})