# apps/warehouse/utils/warehouse_selector.py
from apps.inventory.models import InventoryStock
from django.db.models import Q

def choose_best_warehouse_for_order(order_items, candidate_warehouses=None):
    """
    Simple warehouse selection strategy:
    - candidate_warehouses: optional queryset/list of warehouse ids to consider
    - order_items: list of dicts: [{'sku_id': <uuid>, 'qty': 2}, ...]
    Returns: warehouse_id or raises ValueError if none suitable.
    Strategy implemented:
    1) prefer warehouses that have all SKUs available (available_qty >= needed)
    2) if none have all, choose warehouse with max number of SKUs covered and sufficient overall qty
    3) fallback: choose first warehouse with at least one item.
    This is a simple strategy — replace with geo + load + TTLed metrics for production.
    """
    sku_ids = [it['sku_id'] for it in order_items]
    # Build counts per warehouse
    # Query InventoryStock for the SKUs
    stocks = InventoryStock.objects.filter(sku_id__in=sku_ids)
    if candidate_warehouses:
        stocks = stocks.filter(warehouse_id__in=candidate_warehouses)

    # Map: warehouse -> {sku_id: available_qty}
    wh_map = {}
    for s in stocks:
        wh = s.warehouse_id
        wh_map.setdefault(wh, {})[s.sku_id] = s.available_qty

    # Check for warehouse that satisfies all SKUs
    for wh, sku_map in wh_map.items():
        ok = True
        for it in order_items:
            avl = sku_map.get(it['sku_id'], 0)
            if avl < it['qty']:
                ok = False
                break
        if ok:
            return wh

    # otherwise pick warehouse with highest total coverage (sum of min(avail, needed))
    best_wh = None
    best_score = -1
    for wh, sku_map in wh_map.items():
        score = 0
        for it in order_items:
            avl = sku_map.get(it['sku_id'], 0)
            score += min(avl, it['qty'])
        if score > best_score:
            best_score = score
            best_wh = wh

    if best_wh is None:
        raise ValueError("No candidate warehouses have any stock for given SKUs")

    return best_wh
