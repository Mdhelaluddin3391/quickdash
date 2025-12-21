import math
from apps.warehouse.models import Warehouse

class WarehouseSelector:
    """
    Service to find the nearest active warehouse for a given lat/lng.
    """

    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance in kilometers between two points 
        on the earth (specified in decimal degrees).
        """
        # Convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = map(math.radians, [float(lon1), float(lat1), float(lon2), float(lat2)])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r

    @classmethod
    def get_serviceable_warehouse(cls, lat, lng):
        """
        Returns the nearest active warehouse if within service radius.
        Returns None if no warehouse serves this area.
        """
        warehouses = Warehouse.objects.filter(is_active=True)
        nearest_wh = None
        min_dist = float('inf')

        for wh in warehouses:
            # Skip if warehouse has no coordinates
            if not wh.latitude or not wh.longitude:
                continue

            dist = cls.haversine_distance(lat, lng, wh.latitude, wh.longitude)

            # Check strict radius (e.g., Warehouse defined radius or default 5km)
            # Assuming warehouse.service_radius exists, else default to 5.0
            radius = getattr(wh, 'service_radius', 5.0) 

            if dist <= radius and dist < min_dist:
                min_dist = dist
                nearest_wh = wh

        return nearest_wh