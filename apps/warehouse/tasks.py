# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger 
from apps.inventory.services import find_best_warehouse_for_items
from apps.warehouse.services import reserve_stock_for_order
from apps.warehouse.notifications import notify_picker_new_task

logger = get_task_logger(__name__) 

def _cancel_failed_order(order_id, reason):
    """
    Helper to safely cancel an order if orchestration fails.
    """
    try:
        from apps.orders.models import Order
        from apps.orders.services import cancel_order
        
        # Order fetch karein
        order = Order.objects.get(id=order_id)
        
        # Cancel logic call karein
        cancel_order(order, cancelled_by="SYSTEM", reason=reason)
        
        logger.info(f"Order {order_id} auto-cancelled due to fulfillment failure: {reason}")
    except Exception as ex:
        logger.error(f"Failed to auto-cancel order {order_id}: {ex}")

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
            _cancel_failed_order(order_id, "No matching warehouse found with stock.")
            return "No Warehouse Found"
        warehouse_id = str(wh.id)

    try:
        # Reserve stock (PickingTask create karega)
        pick_task = reserve_stock_for_order(order_id, warehouse_id, items)
        
        # Picker ko notify karo
        notify_picker_new_task(pick_task)
        
        logger.info(f"Orchestration successful for Order {order_id}. Task: {pick_task.id}")
        return str(pick_task.id)
        
    except Exception as e:
        logger.exception(f"Orchestration Error for Order {order_id}: {e}")
        
        # CRITICAL: Order cancel karo agar WMS fail ho gaya
        _cancel_failed_order(order_id, f"Allocation Failed: {str(e)}")
        
        # Error ko propagate karein taaki Celery ko pata chale task fail hua
        raise e