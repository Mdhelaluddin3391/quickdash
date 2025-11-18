# apps/warehouse/notifications.py
"""
Very simple placeholder – right now just logs.
Replace with Redis / Kafka / WebSocket / FCM etc. later.
"""
import logging

logger = logging.getLogger(__name__)


def notify_picker_new_task(picking_task):
    payload = {
        "type": "new_pick_task",
        "task_id": str(picking_task.id),
        "order_id": picking_task.order_id,
        "warehouse_id": str(picking_task.warehouse_id),
    }
    logger.info("Notify picker: %s", payload)


def notify_packer_new_task(packing_task):
    payload = {
        "type": "new_pack_task",
        "packing_task_id": str(packing_task.id),
        "order_id": packing_task.picking_task.order_id,
        "warehouse_id": str(packing_task.picking_task.warehouse_id),
    }
    logger.info("Notify packer: %s", payload)


def notify_dispatch_ready(dispatch_record):
    payload = {
        "type": "dispatch_ready",
        "dispatch_id": str(dispatch_record.id),
        "order_id": dispatch_record.order_id,
        "warehouse_id": str(dispatch_record.warehouse_id),
    }
    logger.info("Notify dispatch: %s", payload)


def notify_packer_new_task(packing_task): # <-- YEH FUNCTION ADD KAREIN
    payload = {
        "type": "new_pack_task",
        "packing_task_id": str(packing_task.id),
        "order_id": packing_task.picking_task.order_id,
        "warehouse_id": str(packing_task.picking_task.warehouse_id),
    }
    logger.info("Notify packer: %s", payload)