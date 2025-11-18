# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger 
# ... (existing imports, ensure obsolete imports removed)

logger = get_task_logger(__name__) 


@shared_task
def orchestrate_order_fulfilment_from_order_payload(payload):
    """
    payload example:
    {
      "order_id": "O123",
      "warehouse_id": "<uuid optional>",
      "items": [
        {"sku_id": "<uuid>", "qty": 2},
        ...
      ],
      "metadata": {...}
    }
    """
    order_id = payload["order_id"]
    items = payload["items"]
    warehouse_id = payload.get("warehouse_id")

    if warehouse_id is None:
        wh = select_best_warehouse(items)
        warehouse_id = str(wh.id)

    allocations = reserve_stock_for_order(order_id, warehouse_id, items)
    pick_task = create_picking_task_from_reservation(order_id, warehouse_id, allocations)

    notify_picker_new_task(pick_task)
    return str(pick_task.id)


# --- YEH DONO FUNCTION AB apps/payments/tasks.py MEIN HAI ---
# def send_refund_webhook(self, fc_id, refund_payload):
# def process_admin_refund_task(self, order_id, amount=None, reason=""):
# In dono functions ko yahan se hata diya gaya hai.