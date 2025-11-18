# apps/inventory/services.py
from django.db.models import Sum
from .models import InventoryStock
from apps.warehouse.models import Warehouse

def find_best_warehouse_for_items(order_items):
    """
    Logic moved from warehouse app to here.
    Inventory app knows best about stock levels.
    """
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
        return None # Handle gracefully
        
    return Warehouse.objects.get(id=best_wh_id)