# apps/inventory/services.py
from django.db import transaction
from django.db.models import Sum

from .models import InventoryStock
from apps.warehouse.models import Warehouse

from django.db import transaction
from django.db.models import F
from .models import InventoryStock
from apps.warehouse.models import Warehouse

def check_and_lock_inventory(warehouse_id, sku_id, qty_needed):
    """
    Optimistic Locking approach for higher concurrency.
    Returns True if stock was secured, raises ValueError otherwise.
    """
    # Try to atomically decrement stock where available >= needed
    rows_updated = InventoryStock.objects.filter(
        warehouse_id=warehouse_id,
        sku_id=sku_id,
        available_qty__gte=qty_needed
    ).update(
        available_qty=F('available_qty') - qty_needed,
        # We might not want to touch reserved_qty here if this is just a 'lock'
        # validation step, but usually, lock means 'reserve'.
        # Assuming we just want to ensure stock exists for now:
    )

    if rows_updated == 0:
        # Check if it was existence issue or stock issue
        exists = InventoryStock.objects.filter(warehouse_id=warehouse_id, sku_id=sku_id).exists()
        if not exists:
            raise ValueError(f"SKU {sku_id} not found in warehouse {warehouse_id}.")
        raise ValueError(f"Insufficient stock for SKU {sku_id}.")

    # If we strictly need to just "Check" without modifying state yet (as implied by name),
    # then select_for_update is required but creates the bottleneck.
    # Ideally, rename this to 'reserve_inventory' and keep the update.
    # For the specific 'check' context in create_order_from_cart:
    
    # Revert the decrement if this function was purely meant for checking (Validation)
    # But validation without reservation is prone to race conditions immediately after.
    # Recommendation: This function SHOULD reserve/hold the stock.
    
    return True


def find_best_warehouse_for_items(order_items):
    """
    Inventory microservice ka core 'router'.

    order_items = [
        {"sku_id": <uuid|int>, "qty": <int>},
        ...
    ]

    Logic (simple but practical):
    - Active warehouses fetch karo
    - InventoryStock se aggregated availability dekh ke:
        * warehouse ko score do based on how much demand it can satisfy
        * best score wala warehouse pick karo
    - Agar koi warehouse saare SKUs ke liye availability nahi deta, None return.

    Used by:
    - apps.warehouse.tasks.orchestrate_order_fulfilment_from_order_payload
      (if order me explicit warehouse nahi diya) :contentReference[oaicite:4]{index=4}
    """
    candidate_warehouses = Warehouse.objects.filter(is_active=True)
    if not candidate_warehouses.exists():
        return None

    sku_ids = [it["sku_id"] for it in order_items]

    stocks = (
        InventoryStock.objects.filter(
            warehouse__in=candidate_warehouses,
            sku_id__in=sku_ids,
            available_qty__gt=0,
        )
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

        if not eligible:
            continue

        if score > best_score:
            best_score = score
            best_wh_id = wh.id

    if best_wh_id is None:
        return None

    return Warehouse.objects.get(id=best_wh_id)
