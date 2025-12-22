# apps/inventory/services.py

import logging
from typing import List, Dict
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError

from .models import InventoryStock, StockMovementLog
from apps.utils.exceptions import OutOfStockError

logger = logging.getLogger(__name__)


class InventoryService:
    """
    Inventory Domain Service
    Concurrency-safe and transactionally correct.
    """

    @staticmethod
    @transaction.atomic
    def bulk_lock_and_validate(
        warehouse_id: int,
        items: List[Dict[str, int]],
    ) -> Dict[int, InventoryStock]:
        """
        Lock inventory rows deterministically and validate availability.
        """
        sorted_items = sorted(items, key=lambda x: x["product_id"])
        product_ids = [i["product_id"] for i in sorted_items]
        qty_map = {i["product_id"]: i["quantity"] for i in sorted_items}

        stocks = (
            InventoryStock.objects
            .select_for_update()
            .filter(warehouse_id=warehouse_id, product_id__in=product_ids)
        )

        stock_map = {s.product_id: s for s in stocks}

        for product_id, qty in qty_map.items():
            stock = stock_map.get(product_id)
            if not stock:
                raise OutOfStockError(f"Product {product_id} not found in warehouse")

            available = stock.quantity - stock.reserved_quantity
            if available < qty:
                raise OutOfStockError(
                    f"Insufficient stock for {stock.product.name}"
                )

        return stock_map

    @staticmethod
    @transaction.atomic
    def reserve_stock(
        warehouse_id: int,
        items: List[Dict[str, int]],
        reference: str,
    ):
        stocks = InventoryService.bulk_lock_and_validate(
            warehouse_id=warehouse_id,
            items=items,
        )

        logs = []
        for product_id, stock in stocks.items():
            qty = next(i["quantity"] for i in items if i["product_id"] == product_id)

            stock.reserved_quantity = F("reserved_quantity") + qty
            stock.save(update_fields=["reserved_quantity", "updated_at"])

            logs.append(
                StockMovementLog(
                    inventory=stock,
                    quantity_change=0,
                    movement_type=StockMovementLog.MovementType.RESERVATION,
                    reference=reference,
                    balance_after=stock.quantity,
                )
            )

        StockMovementLog.objects.bulk_create(logs)

    @staticmethod
    @transaction.atomic
    def release_stock(
        warehouse_id: int,
        items: List[Dict[str, int]],
        reference: str,
    ):
        sorted_items = sorted(items, key=lambda x: x["product_id"])
        product_ids = [i["product_id"] for i in sorted_items]
        qty_map = {i["product_id"]: i["quantity"] for i in sorted_items}

        stocks = (
            InventoryStock.objects
            .select_for_update()
            .filter(warehouse_id=warehouse_id, product_id__in=product_ids)
        )

        logs = []
        for stock in stocks:
            qty = qty_map.get(stock.product_id, 0)
            stock.reserved_quantity = F("reserved_quantity") - qty
            stock.save(update_fields=["reserved_quantity", "updated_at"])

            logs.append(
                StockMovementLog(
                    inventory=stock,
                    quantity_change=0,
                    movement_type=StockMovementLog.MovementType.RELEASE,
                    reference=reference,
                    balance_after=stock.quantity,
                )
            )

        StockMovementLog.objects.bulk_create(logs)

    @staticmethod
    @transaction.atomic
    def confirm_deduction(
        warehouse_id: int,
        items: List[Dict[str, int]],
        reference: str,
    ):
        product_ids = [i["product_id"] for i in items]
        qty_map = {i["product_id"]: i["quantity"] for i in items}

        stocks = (
            InventoryStock.objects
            .select_for_update()
            .filter(warehouse_id=warehouse_id, product_id__in=product_ids)
        )

        logs = []
        for stock in stocks:
            qty = qty_map.get(stock.product_id, 0)
            stock.quantity = F("quantity") - qty
            stock.reserved_quantity = F("reserved_quantity") - qty
            stock.save(update_fields=["quantity", "reserved_quantity", "updated_at"])
            stock.refresh_from_db()

            logs.append(
                StockMovementLog(
                    inventory=stock,
                    quantity_change=-qty,
                    movement_type=StockMovementLog.MovementType.OUTBOUND_ORDER,
                    reference=reference,
                    balance_after=stock.quantity,
                )
            )

        StockMovementLog.objects.bulk_create(logs)
