# apps/inventory/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction

from .models import InventoryStock, InventoryHistory

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=10)
@transaction.atomic
def update_inventory_stock_task(
    self,
    sku_id,
    warehouse_id,
    delta_available,
    delta_reserved,
    reference=None,
    change_type=None,
):
    """
    Main Inventory engine:

    - Called from warehouse signals (inventory_change_required)
    - Strong consistency: row-level locking + no negative quantities
    - Writes audit entry in InventoryHistory

    IMPORTANT:
    - Don't call this task from Orders directly.
    - Always go via WMS (Warehouse app) so physical & central stock stay aligned.
    """
    try:
        stock, created = (
            InventoryStock.objects.select_for_update().get_or_create(
                warehouse_id=warehouse_id,
                sku_id=sku_id,
                defaults={"available_qty": 0, "reserved_qty": 0},
            )
        )

        stock.available_qty += int(delta_available)
        stock.reserved_qty += int(delta_reserved)

        if stock.available_qty < 0:
            logger.error(
                "Integrity Error: Available Qty went negative for SKU %s in WH %s",
                sku_id,
                warehouse_id,
            )
            raise ValueError("Available quantity cannot be negative.")

        if stock.reserved_qty < 0:
            logger.error(
                "Integrity Error: Reserved Qty went negative for SKU %s in WH %s",
                sku_id,
                warehouse_id,
            )
            raise ValueError("Reserved quantity cannot be negative.")

        stock.save()

        InventoryHistory.objects.create(
            stock=stock,
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            delta_available=delta_available,
            delta_reserved=delta_reserved,
            available_after=stock.available_qty,
            reserved_after=stock.reserved_qty,
            change_type=change_type or "",
            reference=reference or "",
        )

        logger.info(
            "InventoryStock updated for %s@%s: ΔAvl=%s, ΔRes=%s, type=%s, ref=%s",
            sku_id,
            warehouse_id,
            delta_available,
            delta_reserved,
            change_type,
            reference,
        )

    except Exception as exc:
        logger.exception(
            "Failed to update InventoryStock %s@%s: %s", sku_id, warehouse_id, exc
        )
        # NOTE: when called synchronously, Celery retry nahi chalega,
        # but async .delay() use karoge to retry work karega.
        raise self.retry(exc=exc)
