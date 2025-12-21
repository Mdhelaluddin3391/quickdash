# apps/inventory/services.py
from django.db import transaction
from django.db.models import F
from .models import InventoryStock
from apps.warehouse.models import Warehouse
from django.contrib.gis.geos import Point
from django.db.models import F
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point

@transaction.atomic
def check_and_lock_inventory(warehouse_id, sku_id, qty_needed):
    # Surgical fix: Use select_for_update to ensure the lock persists 
    # until the parent Checkout transaction commits/rolls back.
    stock = InventoryStock.objects.select_for_update().filter(
        warehouse_id=warehouse_id,
        sku_id=sku_id
    ).first()
    
    if not stock or stock.available_qty < qty_needed:
         raise ValueError(f"Insufficient stock for SKU {sku_id}")
    
    stock.available_qty = F('available_qty') - qty_needed
    stock.save(update_fields=['available_qty'])
    return True

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point

def find_best_warehouse_for_items(order_items, customer_location=None):
    """
    Optimized warehouse selection using PostGIS DB-level filtering.
    Eliminates O(N*M) Python loops for distance calculation.
    """
    # 1. Base Query
    warehouses = Warehouse.objects.filter(is_active=True)
    
    # 2. Apply PostGIS Distance Filtering & Sorting (DB Level)
    if customer_location:
        # Normalize input to Point
        if isinstance(customer_location, (tuple, list)):
            pnt = Point(float(customer_location[1]), float(customer_location[0]), srid=4326)
        else:
            pnt = customer_location
            
        # Filter warehouses within reasonable radius (e.g., 20km) to reduce search space
        # and annotate distance for scoring.
        warehouses = warehouses.filter(
            location__dwithin=(pnt, D(km=20))
        ).annotate(
            distance=Distance('location', pnt)
        ).order_by('distance')

    if not warehouses.exists():
        return None

    # 3. Efficient Stock Fetching (Single Query)
    sku_ids = [it["sku_id"] for it in order_items]
    
    # Fetch only relevant stock for candidate warehouses
    stocks = InventoryStock.objects.filter(
        warehouse__in=warehouses,
        sku_id__in=sku_ids,
        available_qty__gt=0
    ).values('warehouse_id', 'sku_id', 'available_qty')

    # 4. In-Memory Scoring (Map Reduce)
    # We now loop over a much smaller dataset (only valid warehouses nearby)
    wh_stock_map = {}
    for row in stocks:
        wh_id = row['warehouse_id']
        if wh_id not in wh_stock_map:
            wh_stock_map[wh_id] = {}
        wh_stock_map[wh_id][str(row['sku_id'])] = row['available_qty']

    best_wh = None
    best_score = -float('inf')

    # Evaluate candidates (already ordered by distance if loc provided)
    for wh in warehouses:
        wh_id = wh.id
        stock_map = wh_stock_map.get(wh_id, {})
        
        score = 0
        fully_fulfillable = True
        
        for item in order_items:
            req_sku = str(item['sku_id'])
            req_qty = int(item['qty'])
            
            avail = stock_map.get(req_sku, 0)
            if avail >= req_qty:
                score += 100
            else:
                fully_fulfillable = False
        
        if fully_fulfillable:
            score += 1000

        # Apply Distance Penalty (if applicable)
        # 1km = 100 points penalty
        if hasattr(wh, 'distance') and wh.distance is not None:
             # distance object .km attribute
             score -= (wh.distance.km * 100)

        if score > best_score:
            best_score = score
            best_wh = wh

    return best_wh


def batch_check_and_lock_inventory(warehouse_id, items_list):
    """Surgical Fix: Lock all required SKUs in one batch query."""
    sku_ids = [item.sku_id for item in items_list]
    # Lock all relevant rows at once
    stocks = InventoryStock.objects.select_for_update().filter(
        warehouse_id=warehouse_id, sku_id__in=sku_ids
    ).order_by('sku_id')