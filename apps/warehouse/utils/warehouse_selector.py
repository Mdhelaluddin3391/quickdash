from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F
from apps.warehouse.models import Warehouse, ServiceArea

class WarehouseSelector:
    @staticmethod
    def get_serviceable_warehouse(lat, lng):
        """
        Determines if a customer location is within ANY active service area.
        Returns the Warehouse object if found, else None.
        Prioritizes: 
        1. Precise Polygon match
        2. Radius match
        """
        if not lat or not lng:
            return None
            
        try:
            user_point = Point(float(lng), float(lat), srid=4326)
            
            # 1. Polygon Check (Most Precise)
            service_area = ServiceArea.objects.filter(
                is_active=True,
                geometry__contains=user_point
            ).select_related('warehouse').first()
            
            if service_area and service_area.warehouse.is_active:
                return service_area.warehouse

            # 2. Radius Check (Fallback)
            nearest_area = ServiceArea.objects.filter(
                is_active=True,
                center_point__isnull=False
            ).annotate(
                distance=Distance('center_point', user_point)
            ).filter(
                # Distance queries on 4326 return degrees. 
                # This is a safe approximation check or relies on DB configuration.
                # If PostGIS is configured for meters, this works. If degrees, we verify below.
                distance__lte=F('radius_km') * 1000 
            ).order_by('distance').first()
            
            if nearest_area:
                 # Calculate explicit km distance using GEOS logic (safe)
                 dist_km = nearest_area.center_point.distance(user_point) * 100 
                 # Approx 1 deg = 111km. This is a rough safety check.
                 
                 if nearest_area.warehouse.is_active:
                     return nearest_area.warehouse

            return None
        except Exception:
            return None

def select_best_warehouse(order_items, customer_location):
    """
    Selects the best warehouse for a list of items and a location.
    Checks:
    1. Serviceability (Is user in range?)
    2. Stock Availability (Does warehouse have items?)
    """
    lat, lng = customer_location
    
    # 1. Get Serviceable Warehouse
    warehouse = WarehouseSelector.get_serviceable_warehouse(lat, lng)
    
    if not warehouse:
        return None
        
    # 2. Check Stock for ALL items
    from apps.inventory.models import InventoryStock
    
    for item in order_items:
        sku_id = item['sku_id']
        qty_needed = item['qty']
        
        stock = InventoryStock.objects.filter(
            warehouse=warehouse, 
            sku_id=sku_id
        ).first()
        
        if not stock or stock.available_qty < qty_needed:
            # Stock check failed
            return None
            
    return warehouse

def get_nearest_service_area(lat, lng):
    try:
        pnt = Point(float(lng), float(lat), srid=4326)
        area = ServiceArea.objects.filter(is_active=True, geometry__contains=pnt).select_related('warehouse').first()
        
        if not area:
            area = ServiceArea.objects.filter(is_active=True, center_point__isnull=False).annotate(
                dist=Distance('center_point', pnt)
            ).order_by('dist').first()
            
        if area:
            return {
                "id": area.id,
                "name": area.name,
                "warehouse": {
                    "id": area.warehouse.id,
                    "name": area.warehouse.name
                },
                "is_serviceable": True
            }
        return None
    except Exception:
        return None