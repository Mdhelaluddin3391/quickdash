# apps/inventory/services.py
from django.db.models import Sum
from django.db import transaction
from .models import InventoryStock
from apps.warehouse.models import Warehouse

def check_and_lock_inventory(warehouse_id, sku_id, qty_needed):
    """
    Warehouse is function ko call karega stock verify karne ke liye.
    Yeh function InventoryStock table ko lock (select_for_update) karega.
    """
    try:
        # Transaction lock taaki race condition na ho
        inv = InventoryStock.objects.select_for_update().get(
            warehouse_id=warehouse_id, 
            sku_id=sku_id
        )
    except InventoryStock.DoesNotExist:
        raise ValueError(f"SKU {sku_id} not found in warehouse {warehouse_id}.")

    if inv.available_qty < qty_needed:
        raise ValueError(f"Insufficient stock for SKU {sku_id}. Need {qty_needed}, Have {inv.available_qty}")

    return True

# ... (baaki ka find_best_warehouse_for_items function waisa hi rakhein)
def find_best_warehouse_for_items(order_items):
    # ... (existing code)
    candidate_warehouses = Warehouse.objects.filter(is_active=True)
    sku_ids = [it["sku_id"] for it in order_items]
    
    stocks = (
        InventoryStock.objects.filter(warehouse__in=candidate_warehouses, sku_id__in=sku_ids)
        .values("warehouse_id", "sku_id")
        .annotate(avail=Sum("available_qty"))
    )

    wh_map = {}
    for row in stocks:
        wh_map.setdefault(row["warehouse_id"], {})[row["sku_id"]] = row["avail"]

    best_wh_id = None
    best_score = -1

    for wh in candidate_warehouses:
        sku_map = wh_map.get(wh.id, {})
        eligible = True
        score = 0
        for it in order_items:
            avl = sku_map.get(it["sku_id"], 0)
            if avl <= 0:
                eligible = False
                break
            score += min(avl, it["qty"])
        
        if not eligible: continue
        
        if score > best_score:
            best_score = score
            best_wh_id = wh.id

    if best_wh_id is None:
        return None 
        
    return Warehouse.objects.get(id=best_wh_id)