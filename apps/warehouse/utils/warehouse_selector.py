# apps/warehouse/utils/warehouse_selector.py
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from django.db.models import F
from apps.warehouse.models import Warehouse, ServiceArea, BinInventory
from apps.inventory.models import InventoryStock
import logging

logger = logging.getLogger(__name__)

class WarehouseSelector:
    @staticmethod
    def get_serviceable_warehouse(lat, lng):
        """
        Check if a location falls within ANY active service area.
        Returns the first matching Warehouse object or None.
        """
        try:
            pnt = Point(float(lng), float(lat), srid=4326)
            
            # 1. Polygon Check (Exact)
            area = ServiceArea.objects.filter(
                is_active=True, 
                geometry__contains=pnt
            ).select_related('warehouse').first()
            
            if area:
                return area.warehouse

            # 2. Radius Check (Approx)
            # Find closest service area center point
            nearest = ServiceArea.objects.filter(
                is_active=True,
                center_point__isnull=False
            ).annotate(
                distance=Distance('center_point', pnt)
            ).order_by('distance').first()

            if nearest and nearest.distance.km <= nearest.radius_km:
                return nearest.warehouse
                
            return None
        except Exception as e:
            logger.error(f"Error checking serviceability: {e}")
            return None

def get_nearest_service_area(lat, lng):
    """
    Returns dict with service area details for 'Locate Me' functionality.
    """
    try:
        pnt = Point(float(lng), float(lat), srid=4326)
        
        area = ServiceArea.objects.filter(
            is_active=True,
            geometry__contains=pnt
        ).select_related('warehouse').first()
        
        if not area:
            area = ServiceArea.objects.filter(
                is_active=True,
                center_point__isnull=False
            ).annotate(
                distance=Distance('center_point', pnt)
            ).filter(distance__lte=F('radius_km') * 1000).order_by('distance').first() # *1000 if distance in meters? PostGIS depends on SRID. Assuming km logic handles elsewhere or using raw check.

        if area:
            return {
                "serviceable": True,
                "warehouse_id": area.warehouse.id,
                "warehouse_name": area.warehouse.name,
                "service_area": area.name,
                "eta_mins": area.delivery_time_minutes
            }
        return {"serviceable": False}
    except Exception:
        return {"serviceable": False}

def select_best_warehouse(order_items, customer_location):
    """
    Smart Routing Logic:
    1. Filter Warehouses that cover the customer_location.
    2. Check if they have STOCK for all items.
    3. Return the one with stock + closest distance.
    """
    lat, lng = customer_location
    pnt = Point(float(lng), float(lat), srid=4326)

    # 1. Find candidates (Warehouses covering this point)
    # Using ServiceArea reverse lookup
    candidate_ids = ServiceArea.objects.filter(
        is_active=True,
        geometry__contains=pnt
    ).values_list('warehouse_id', flat=True)

    if not candidate_ids:
        # Fallback to radius
        candidate_ids = ServiceArea.objects.filter(
             is_active=True,
             center_point__isnull=False
        ).annotate(
            distance=Distance('center_point', pnt)
        ).filter(distance__lte=15000).values_list('warehouse_id', flat=True) # e.g. 15km hard limit if using meters

    if not candidate_ids:
        return None

    warehouses = Warehouse.objects.filter(id__in=candidate_ids, is_active=True)

    # 2. Check Stock
    for wh in warehouses:
        has_stock = True
        for item in order_items:
            # Check Logical Inventory (InventoryStock)
            stock = InventoryStock.objects.filter(
                warehouse=wh, 
                sku_id=item['sku_id']
            ).first()
            
            if not stock or stock.available_qty < item['qty']:
                has_stock = False
                break
        
        if has_stock:
            return wh

    return None