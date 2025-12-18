# apps/inventory/services.py
from django.db import transaction
from django.db.models import F
from .models import InventoryStock
from apps.warehouse.models import Warehouse
from django.contrib.gis.geos import Point
from django.db.models import F

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

def find_best_warehouse_for_items(order_items, customer_location=None):
    """
    Finds the warehouse that can fulfill the maximum number of items.
    FIX: If customer_location is provided, prioritize distance.
    """
    candidate_warehouses = Warehouse.objects.filter(is_active=True)
    if not candidate_warehouses.exists():
        return None

    sku_ids = [it["sku_id"] for it in order_items]
    
    # 1. Fetch all stock
    stocks = InventoryStock.objects.filter(
        warehouse__in=candidate_warehouses,
        sku_id__in=sku_ids,
        available_qty__gt=0
    ).select_related('warehouse').values(
        'warehouse_id', 'sku_id', 'available_qty', 
        'warehouse__location' # Fetch location
    )

    # 2. Build Map & Warehouse Info
    wh_stock_map = {}
    wh_locations = {}
    
    for row in stocks:
        wh_id = row['warehouse_id']
        sku_id = str(row['sku_id'])
        qty = row['available_qty']
        
        if wh_id not in wh_stock_map:
            wh_stock_map[wh_id] = {}
            wh_locations[wh_id] = row['warehouse__location'] # Store location
            
        wh_stock_map[wh_id][sku_id] = qty

    best_wh_id = None
    best_score = -float('inf')
    
    # 3. Score warehouses
    for wh_id, stock_map in wh_stock_map.items():
        score = 0
        fully_fulfillable = True
        
        for item in order_items:
            req_sku = str(item['sku_id'])
            req_qty = int(item['qty'])
            
            avail = stock_map.get(req_sku, 0)
            if avail >= req_qty:
                score += 100 # Base score for fulfillment
            else:
                fully_fulfillable = False
        
        # Bonus for full fulfillment
        if fully_fulfillable:
            score += 1000

        # FIX: Distance Penalty
        if customer_location and wh_locations.get(wh_id):
            try:
                # Ensure customer_location is a Point
                if isinstance(customer_location, (tuple, list)):
                    pnt = Point(float(customer_location[1]), float(customer_location[0]), srid=4326)
                else:
                    pnt = customer_location
                
                wh_pnt = wh_locations[wh_id]
                if wh_pnt and pnt:
                    dist_km = wh_pnt.distance(pnt) * 100 # Approx degree to KM factor or use .distance().km if projected
                    # Heuristic: Subtract 1 point per km
                    score -= dist_km
            except Exception:
                pass # Fallback to availability only

        if score > best_score:
            best_score = score
            best_wh_id = wh_id

    if best_wh_id:
        return Warehouse.objects.get(id=best_wh_id)
    
    return None


def batch_check_and_lock_inventory(warehouse_id, items_list):
    """Surgical Fix: Lock all required SKUs in one batch query."""
    sku_ids = [item.sku_id for item in items_list]
    # Lock all relevant rows at once
    stocks = InventoryStock.objects.select_for_update().filter(
        warehouse_id=warehouse_id, sku_id__in=sku_ids
    ).order_by('sku_id')