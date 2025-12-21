# apps/warehouse/utils/warehouse_selector.py

from django.db.models import Sum, F
from django.contrib.gis.measure import D
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from apps.inventory.models import InventoryStock
from apps.warehouse.models import Warehouse

def select_best_warehouse(order_items, customer_location=None):
    """
    Selects the optimal warehouse based on:
    1. Capability (Must have stock)
    2. Proximity (Geo-spatial trust)
    3. Score (Coverage - Distance Penalty)
    
    order_items: list of dicts {'sku_id': uuid, 'qty': int}
    customer_location: tuple (lat, lng) or Point object
    """
    
    # 1. Spatial Filtering (Geo-Logic Trust)
    warehouses = Warehouse.objects.filter(is_active=True)
    
    if customer_location:
        if isinstance(customer_location, (tuple, list)):
            pnt = Point(float(customer_location[1]), float(customer_location[0]), srid=4326)
        else:
            pnt = customer_location
            
        # Filter: Only warehouses within 20km
        warehouses = warehouses.filter(
            location__dwithin=(pnt, D(km=20))
        ).annotate(
            dist=Distance('location', pnt)
        ).order_by('dist')
    
    # Early exit if no service
    if not warehouses.exists():
        return None

    # 2. Stock Availability Check (Batch Query)
    sku_ids = [it['sku_id'] for it in order_items]
    
    # Get all relevant stock lines for these warehouses
    stocks = InventoryStock.objects.filter(
        warehouse__in=warehouses,
        sku_id__in=sku_ids
    ).values('warehouse_id', 'sku_id', 'available_qty')

    # Build Map: { wh_id: { sku_id: qty } }
    wh_stock_map = {}
    for s in stocks:
        wh_id = s['warehouse_id']
        if wh_id not in wh_stock_map:
            wh_stock_map[wh_id] = {}
        wh_stock_map[wh_id][str(s['sku_id'])] = s['available_qty']

    # 3. Scoring Algorithm
    best_wh = None
    best_score = -float('inf')

    for wh in warehouses:
        stock_map = wh_stock_map.get(wh.id, {})
        
        current_score = 0
        fully_stocked = True
        
        for item in order_items:
            req_sku = str(item['sku_id'])
            req_qty = item['qty']
            
            avail = stock_map.get(req_sku, 0)
            
            # Critical: If any item is missing entirely, this warehouse is invalid
            # (Unless we support split shipments, but assuming Atomic Orders for now)
            if avail < req_qty:
                fully_stocked = False
                # Penalize heavily, but don't discard if it's the only option (partial fill logic)
                current_score -= 5000 
            else:
                current_score += 100 # Bonus for having stock
        
        if fully_stocked:
            current_score += 1000

        # Apply Distance Penalty: -10 points per km
        if hasattr(wh, 'dist') and wh.dist is not None:
            # .km attribute access on Distance object
            current_score -= (wh.dist.km * 10)

        if current_score > best_score:
            best_score = current_score
            best_wh = wh

    # 4. Final Validation
    # If the best score is significantly negative, it means we can't fulfill the order
    if best_score < -4000:
        return None

    return best_wh