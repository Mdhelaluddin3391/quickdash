# apps/warehouse/signals.py
from django.dispatch import receiver, Signal
from django.conf import settings
import logging
from .models import PickingTask
from .services import create_packing_task_from_picking
from .tasks import orchestrate_order_fulfilment_from_order_payload
from .notifications import notify_packer_new_task
from .tasks import orchestrate_order_fulfilment_from_order_payload
# Custom signal that other apps can send if they don't use Django Order model:
# send_order_created.send(sender=..., order_id=..., order_items=[{sku_id, qty}], metadata={...})
# send_order_created = Signal(providing_args=["order_id", "order_items", "metadata"])
send_order_created = Signal()
logger = logging.getLogger(__name__)



@receiver(send_order_created)
def on_order_created_signal(sender, order_id, order_items, metadata=None, **kwargs):
    """
    Receiver for custom send_order_created signal.
    It enqueues the orchestrator Celery task.
    """
    logger.info("Received send_order_created signal for order %s", order_id)
    try:
        # Fire-and-forget orchestration
        orchestrate_order_fulfilment_from_order_payload.delay({
            "order_id": str(order_id),
            "items": order_items,
            "metadata": metadata or {}
        })
    except Exception:
        logger.exception("Failed to enqueue orchestration task for order %s", order_id)


# If you have an Order model in 'orders' app, auto connect to its post_save
try:
    from django.db.models.signals import post_save
    from django.apps import apps
    Order = apps.get_model('orders', 'Order')
    if Order is not None:
        @receiver(post_save, sender=Order)
        def on_order_model_created(sender, instance, created, **kwargs):
            if not created:
                return
            # Build items list expected by pipeline:
            # Adjust according to your OrderItem model structure
            items = []
            try:
                # try common structure: instance.items.all() with sku_id and qty
                for oi in getattr(instance, 'items').all():
                    sku_id = getattr(oi, 'sku_id', None) or getattr(oi, 'sku', None) and getattr(oi.sku, 'id', None)
                    qty = getattr(oi, 'qty', None) or getattr(oi, 'quantity', None)
                    if sku_id and qty:
                        items.append({"sku_id": str(sku_id), "qty": qty})
            except Exception:
                # If the Order model structure is different, you can instead send the custom signal from orders app.
                logging.exception("Could not auto-build items list from Order instance; please use send_order_created signal from orders app")
                return

            orchestrate_order_fulfilment_from_order_payload.delay({
                "order_id": str(instance.pk),
                "items": items,
                "metadata": {}
            })
except LookupError:
    # orders app not present - skip
    pass
except Exception:
    logger.exception("Error wiring Order model signal")



@receiver(post_save, sender=PickingTask)
def on_picking_task_completed(sender, instance, **kwargs):
    # If picking completed, create packing task async
    if instance.status == 'completed':
        # call via Celery to avoid long sync call
        create_packing_for_pick_task.delay(str(instance.id))

@shared_task
def create_packing_for_pick_task(pick_task_id):
    try:
        pack = create_packing_task_from_picking(pick_task_id)
        notify_packer_new_task(pack)
    except Exception:
        import logging
        logging.exception("Failed to import warehouse signals")
