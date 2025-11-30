# apps/inventory/services.py
from django.db import transaction
from django.db.models import F, Sum, Q, Count
from .models import InventoryStock
from apps.warehouse.models import Warehouse

def check_and_lock_inventory(warehouse_id, sku_id, qty_needed):
    """
    Optimistic Locking approach.
    Updates available stock only if sufficient quantity exists.
    """
    rows_updated = InventoryStock.objects.filter(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        available_qty__gte=qty_needed
    ).update(
        available_qty=F('available_qty') - qty_needed,
        # We assume reserving increases reserved_qty logic happens elsewhere 
        # or via direct task logic. Here we just decrement availability
        # to prevent double-selling.
    )

    if rows_updated == 0:
        # Check specific reason for better error msg
        if not InventoryStock.objects.filter(warehouse_id=warehouse_id, sku_id=sku_id).exists():
            raise ValueError(f"SKU {sku_id} not stocked in warehouse {warehouse_id}.")
        raise ValueError(f"Insufficient stock for SKU {sku_id} in warehouse {warehouse_id}.")

    return True


def find_best_warehouse_for_items(order_items):
    """
    Finds the warehouse that can fulfill the maximum number of items.
    
    OPTIMIZATION:
    Instead of iterating in Python, we use DB aggregation to score warehouses.
    Score = Sum of fillable items.
    """
    candidate_warehouses = Warehouse.objects.filter(is_active=True)
    if not candidate_warehouses.exists():
        return None

    sku_ids = [it["sku_id"] for it in order_items]
    
    # 1. Get stock levels for all relevant SKUs across all active warehouses
    # This single query replaces the N+1 loop.
    stocks = (
        InventoryStock.objects.filter(
            warehouse__in=candidate_warehouses,
            sku_id__in=sku_ids,
            available_qty__gt=0,
        )
        .values("warehouse_id", "sku_id", "available_qty")
    )

    # 2. Build map in memory (much faster than DB queries in loop)
    # structure: { warehouse_id: { sku_id: qty } }
    wh_stock_map = {}
    for row in stocks:
        wh_id = row['warehouse_id']
        if wh_id not in wh_stock_map:
            wh_stock_map[wh_id] = {}
        wh_stock_map[wh_id][str(row['sku_id'])] = row['available_qty']

    best_wh = None
    best_score = -1
    
    # 3. Score Logic (CPU bound, fast)
    # Score = total items fully fulfillable
    # You can adapt this to 'percent fulfillment' logic if partial orders are allowed.
    for wh_id, stock_map in wh_stock_map.items():
        score = 0
        is_fully_fulfillable = True
        
        for item in order_items:
            req_sku = str(item['sku_id'])
            req_qty = int(item['qty'])
            
            avail = stock_map.get(req_sku, 0)
            
            if avail >= req_qty:
                score += 1
            else:
                is_fully_fulfillable = False
                # If strict, break here. If partial allowed, continue.
                # Assuming strict for now:
                
        # Heuristic: Prefer Fully Fulfillable > Highest Item Count
        final_score = score + (1000 if is_fully_fulfillable else 0)
        
        if final_score > best_score:
            best_score = final_score
            best_wh = wh_id

    if best_wh:
        return Warehouse.objects.get(id=best_wh)
    
    return None