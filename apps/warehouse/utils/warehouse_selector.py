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
    2. Proximity (Within 10km ONLY)
    3. Score (Stock availability - Distance Penalty)
    
    order_items: list of dicts {'sku_id': uuid, 'qty': int}
    customer_location: tuple (lat, lng)
    """
    
    # 1. Spatial Filtering (STRICT 10KM LIMIT)
    warehouses = Warehouse.objects.filter(is_active=True)
    
    if customer_location:
        # Tuple (lat, lng) ko Point object mein convert karein
        # Note: Point(lng, lat) hota hai standard GIS mein
        if isinstance(customer_location, (tuple, list)):
            pnt = Point(float(customer_location[1]), float(customer_location[0]), srid=4326)
        else:
            pnt = customer_location
            
        # FILTER: Sirf 10km radius wale warehouses
        warehouses = warehouses.filter(
            location__dwithin=(pnt, D(km=10))
        ).annotate(
            dist=Distance('location', pnt)
        ).order_by('dist')
    
    # Agar 10km mein koi warehouse nahi hai, toh turant return karein
    if not warehouses.exists():
        return None

    # 2. Stock Availability Check (Batch Query)
    sku_ids = [it['sku_id'] for it in order_items]
    
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
            
            # Critical: Agar ek bhi item missing hai, toh heavy penalty
            if avail < req_qty:
                fully_stocked = False
                current_score -= 5000  # Penalty for missing items
            else:
                current_score += 100   # Bonus for having item
        
        if fully_stocked:
            current_score += 1000 # Jackpot bonus for full order

        # Apply Distance Penalty: -10 points per km (Jitna paas, utna behtar)
        if hasattr(wh, 'dist') and wh.dist is not None:
            current_score -= (wh.dist.km * 10)

        if current_score > best_score:
            best_score = current_score
            best_wh = wh

    # 4. Final Validation
    # Agar best score bhi bahut negative hai (matlab items out of stock hain),
    # toh None return karein taaki user ko error dikhe.
    if best_score < -4000:
        return None

    return best_wh