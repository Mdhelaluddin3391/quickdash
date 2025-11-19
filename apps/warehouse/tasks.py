# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger 
from apps.inventory.services import find_best_warehouse_for_items

# --- MISSING IMPORTS ADDED ---
from .services import reserve_stock_for_order, create_picking_task_from_reservation
from .notifications import notify_picker_new_task
# -----------------------------

logger = get_task_logger(__name__) 

@shared_task
def orchestrate_order_fulfilment_from_order_payload(payload):
    order_id = payload["order_id"]
    items = payload["items"]
    warehouse_id = payload.get("warehouse_id")

    # Agar warehouse_id nahi diya, to Inventory App se poocho
    if warehouse_id is None:
        wh = find_best_warehouse_for_items(items)
        if not wh:
            logger.error(f"No warehouse found for Order {order_id}")
            return "No Warehouse Found"
        warehouse_id = str(wh.id)

    # Ab ye functions chalenge kyunki imports add kar diye hain
    allocations = reserve_stock_for_order(order_id, warehouse_id, items)
    pick_task = create_picking_task_from_reservation(order_id, warehouse_id, allocations)

    notify_picker_new_task(pick_task)
    return str(pick_task.id)