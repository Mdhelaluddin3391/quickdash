# apps/warehouse/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger  # <-- FIX: Import add kiya
import requests  # <-- FIX: Import add kiya
from django.conf import settings  # <-- FIX: Import add kiya

from apps.warehouse.models import Warehouse
from .services import (
    reserve_stock_for_order,
    create_picking_task_from_reservation,
)
from .utils.warehouse_selector import select_best_warehouse
from .notifications import notify_picker_new_task

logger = get_task_logger(__name__)  # <-- FIX: Logger add kiya


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


# --- FIX: YEH POORA FUNCTION MISSING THA ---
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
        return {'status': 'ok', 'response': r.text}
    except Exception as exc:
        logger.exception("Refund webhook failed, will retry")
        raise self.retry(exc=exc)