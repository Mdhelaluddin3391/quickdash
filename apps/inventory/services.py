# apps/inventory/services.py
from django.db import transaction
from django.db.models import Sum

from .models import InventoryStock
from apps.warehouse.models import Warehouse


def check_and_lock_inventory(warehouse_id, sku_id, qty_needed):
    """
    HARD LOCK:

    - WMS ya Orders orchestration yeh function transaction ke andar call karein.
    - select_for_update() se InventoryStock row lock ho jaata hai.
    - Agar available_qty < qty_needed ho to ValueError raise ho jaata hai.

    NOTE:
    - Yeh sirf validation hai; actual reservation/physical movement WMS kar raha hai
      (BinInventory + StockMovement + inventory_change_required signal).
    """
    with transaction.atomic():
        try:
            inv = (
                InventoryStock.objects.select_for_update()
                .select_related("warehouse", "sku")
                .get(
                    warehouse_id=warehouse_id,
                    sku_id=sku_id,
                )
            )
        except InventoryStock.DoesNotExist:
            raise ValueError(
                f"SKU {sku_id} not found in warehouse {warehouse_id} (InventoryStock)."
            )

        if inv.available_qty < qty_needed:
            raise ValueError(
                f"Insufficient stock for SKU {sku_id}. Need {qty_needed}, "
                f"Have {inv.available_qty}"
            )

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
