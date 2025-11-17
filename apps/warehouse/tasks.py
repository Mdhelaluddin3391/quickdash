# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from .utils.warehouse_selector import choose_best_warehouse_for_order
from .services import reserve_stock_for_order, create_picking_task_from_reservation, create_packing_task_from_picking, complete_packing, assign_dispatch
from .notifications import notify_picker_new_task, notify_packer_new_task, notify_dispatch_ready
from .exceptions import NoAvailableWarehouseError, ReservationFailedError
import time
from celery import shared_task
import requests
from django.conf import settings
from celery.utils.log import get_task_logger
from django.db import transaction
from .warehouse_selector import choose_best_warehouse_for_order # <-- YEH SAHI HAI
from .services import reserve_stock_for_order, create_picking_task_from_reservation, create_packing_task_from_picking, complete_packing, assign_dispatch

logger = get_task_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def orchestrate_order_fulfilment_from_order_payload(self, payload):
    """
    Payload shape:
    {
      "order_id": "<id>",
      "items": [ {"sku_id": "<uuid>", "qty": 2}, ... ],
      "metadata": {...}
    }
    This is the single entrypoint to automate the full pipeline:
    1) choose warehouse
    2) reserve stock (db txn)
    3) create picking task
    4) notify picker
    (subsequent steps triggered by pick/pack actions or chained tasks)
    """
    order_id = payload.get('order_id')
    items = payload.get('items', [])
    metadata = payload.get('metadata', {})

    logger.info("Orchestration started for order %s", order_id)

    # basic sanity
    if not items:
        logger.error("Order %s has no items; abort", order_id)
        return {"status":"no_items"}

    # Choose warehouse (this can raise ValueError)
    try:
        warehouse_id = choose_best_warehouse_for_order(items)
    except Exception as e:
        logger.exception("No suitable warehouse found for order %s", order_id)
        raise self.retry(exc=e)

    # Reserve stock. This may raise OutOfStockError from services
    try:
        allocations = reserve_stock_for_order(order_id, warehouse_id, items)
    except Exception as e:
        logger.exception("Reservation failed for order %s: %s", order_id, e)
        # retry a few times in case of concurrency races or temp db locks
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            # convert to more specific error
            raise ReservationFailedError(f"Reservation failed after retries for order {order_id}")

    # Create picking task from allocations
    try:
        pick_task = create_picking_task_from_reservation(order_id, warehouse_id, allocations)
    except Exception as e:
        logger.exception("Failed to create picking task for order %s", order_id)
        # In production you might want to rollback reservation or create incident
        raise

    # Notify pickers / push to queue
    try:
        notify_picker_new_task(pick_task)
    except Exception:
        logger.exception("Failed to notify picker for task %s", pick_task.id)

    # Optionally chain creation of packing & dispatch after pick completion by listening to task completion events
    logger.info("Orchestration complete for order %s: pick_task=%s", order_id, pick_task.id)
    return {"status":"ok", "order_id": order_id, "pick_task_id": str(pick_task.id)}





@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_refund_webhook(self, fc_id, refund_payload):
    """
    Send refund request to Payments webhook.
    refund_payload is a dict: {order_id, pick_item_id, amount, reason, ...}
    Settings: WMS_REFUND_WEBHOOK_URL should be defined in settings
    """
    url = getattr(settings, 'WMS_REFUND_WEBHOOK_URL', None)
    if not url:
        logger.error("No WMS_REFUND_WEBHOOK_URL set; cannot send refund")
        return {'status': 'no_webhook'}
    try:
        r = requests.post(url, json=refund_payload, timeout=10)
        r.raise_for_status()
        logger.info("Refund webhook success for fc %s", fc_id)
        return {'status':'ok','response': r.text}
    except Exception as exc:
        logger.exception("Refund webhook failed, will retry")
        raise self.retry(exc=exc)
