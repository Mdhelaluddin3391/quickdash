# apps/warehouse/utils/warehouse_selector.py
from django.db.models import Sum
from apps.inventory.models import InventoryStock
from apps.warehouse.models import Warehouse


def select_best_warehouse(order_items, candidate_warehouses=None):
    """
    Very simple selector:
    - filter warehouses that have *some* stock for all SKUs
    - pick the warehouse with the highest total "coverage"
      (sum of min(available, requested) for each sku)
    order_items = [{"sku_id": <uuid>, "qty": int}, ...]
    candidate_warehouses = queryset or list of Warehouses or None
    """
    if candidate_warehouses is None:
        candidate_warehouses = Warehouse.objects.filter(is_active=True)

    sku_ids = [it["sku_id"] for it in order_items]
    stocks = (
        InventoryStock.objects.filter(warehouse__in=candidate_warehouses, sku_id__in=sku_ids)
        .values("warehouse_id", "sku_id")
        .annotate(avail=Sum("available_qty"))
    )

    # build map: warehouse -> {sku_id: avail}
    wh_map = {}
    for row in stocks:
        wh_map.setdefault(row["warehouse_id"], {})[row["sku_id"]] = row["avail"]

    best_wh_id = None
    best_score = -1

    for wh in candidate_warehouses:
        sku_map = wh_map.get(wh.id, {})
        # must have >0 for every sku to be "eligible"
        eligible = True
        score = 0
        for it in order_items:
            avl = sku_map.get(it["sku_id"], 0)
            if avl <= 0:
                eligible = False
                break
            score += min(avl, it["qty"])
        if not eligible:
            continue
        if score > best_score:
            best_score = score
            best_wh_id = wh.id

    if best_wh_id is None:
        raise ValueError("No candidate warehouses can fulfill this order")

    return Warehouse.objects.get(id=best_wh_id)
