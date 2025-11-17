# apps/warehouse/tasks.py
from celery import shared_task

from apps.warehouse.models import Warehouse
from .services import (
    reserve_stock_for_order,
    create_picking_task_from_reservation,
)
from .utils.warehouse_selector import select_best_warehouse
from .notifications import notify_picker_new_task


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
