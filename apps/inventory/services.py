# apps/inventory/services.py
from django.db import transaction
from django.db.models import F
from .models import InventoryStock
from apps.warehouse.models import Warehouse

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

def find_best_warehouse_for_items(order_items):
    """
    Finds the warehouse that can fulfill the maximum number of items.
    """
    candidate_warehouses = Warehouse.objects.filter(is_active=True)
    if not candidate_warehouses.exists():
        return None

    sku_ids = [it["sku_id"] for it in order_items]
    
    # 1. Fetch all stock for these SKUs across all warehouses in one query
    stocks = InventoryStock.objects.filter(
        warehouse__in=candidate_warehouses,
        sku_id__in=sku_ids,
        available_qty__gt=0
    ).values('warehouse_id', 'sku_id', 'available_qty')

    # 2. Build in-memory map: { wh_id: { sku_id: qty } }
    wh_stock_map = {}
    for row in stocks:
        wh_id = row['warehouse_id']
        sku_id = str(row['sku_id'])
        qty = row['available_qty']
        
        if wh_id not in wh_stock_map:
            wh_stock_map[wh_id] = {}
        wh_stock_map[wh_id][sku_id] = qty

    best_wh_id = None
    best_score = -1
    
    # 3. Score warehouses
    for wh_id, stock_map in wh_stock_map.items():
        score = 0
        fully_fulfillable = True
        
        for item in order_items:
            req_sku = str(item['sku_id'])
            req_qty = int(item['qty'])
            
            avail = stock_map.get(req_sku, 0)
            
            if avail >= req_qty:
                score += 1 # Item is fulfillable
            else:
                fully_fulfillable = False
                
        # Scoring weight: Full fulfillment is heavily prioritized
        final_score = score + (1000 if fully_fulfillable else 0)
        
        if final_score > best_score:
            best_score = final_score
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