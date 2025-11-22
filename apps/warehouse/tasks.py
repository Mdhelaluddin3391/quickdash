# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger 
from apps.inventory.services import find_best_warehouse_for_items

# Corrected Imports
from .services import reserve_stock_for_order  # create_picking_task_from_reservation HATA DIYA GAYA HAI
from .notifications import notify_picker_new_task

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

    try:
        # FIX: reserve_stock_for_order ab PickingTask object return karega
        pick_task = reserve_stock_for_order(order_id, warehouse_id, items)
        
        # Picker ko notify karo
        notify_picker_new_task(pick_task)
        
        logger.info(f"Orchestration successful for Order {order_id}. Task: {pick_task.id}")
        return str(pick_task.id)
        
    except Exception as e:
    logger.exception(f"Orchestration Error: {e}")
    # ADD THIS:
    from apps.orders.models import Order
    from apps.orders.services import cancel_order
    
    order = Order.objects.get(id=order_id)
    cancel_order(order, cancelled_by="SYSTEM", reason=f"WMS Allocation Failed: {str(e)}")

def _cancel_failed_order(order_id, reason):
    try:
        from apps.orders.models import Order
        from apps.orders.services import cancel_order
        
        order = Order.objects.get(id=order_id)
        cancel_order(order, cancelled_by="SYSTEM", reason=reason)
        logger.info(f"Order {order_id} auto-cancelled due to fulfillment failure.")
    except Exception as ex:
        logger.error(f"Failed to auto-cancel order {order_id}: {ex}")