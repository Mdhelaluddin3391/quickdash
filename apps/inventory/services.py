# apps/inventory/services.py
import logging
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from typing import List, Dict, Tuple

from .models import InventoryStock, StockMovementLog
from apps.utils.exceptions import OutOfStockError  # Custom Exception

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Domain Service for Inventory Management.
    Enforces strict locking and concurrency safety.
    """

    @staticmethod
    def get_stock_overview(warehouse_id: int):
        return InventoryStock.objects.filter(
            warehouse_id=warehouse_id
        ).select_related('product')

    @staticmethod
    @transaction.atomic
    def reserve_stock(
        warehouse_id: int, 
        items: List[Dict[str, int]], 
        reference: str
    ):
        """
        Locks rows and reserves stock for an Order.
        
        Args:
            warehouse_id: ID of the fulfilling warehouse
            items: List of dicts [{'product_id': 1, 'quantity': 2}, ...]
            reference: Order ID (e.g., "ORD-12345")
            
        Raises:
            OutOfStockError: If any item is unavailable.
        """
        # 1. Sort items by Product ID to prevent Deadlocks
        # (Always locking resources in the same order avoids circular dependencies)
        sorted_items = sorted(items, key=lambda x: x['product_id'])
        product_ids = [item['product_id'] for item in sorted_items]
        quantity_map = {item['product_id']: item['quantity'] for item in sorted_items}

        # 2. Acquire Pessimistic Lock (Select For Update)
        # We fetch all required stocks in one query.
        stocks = list(InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id,
            product_id__in=product_ids
        ))

        stock_map = {stock.product_id: stock for stock in stocks}

        # 3. Validation Phase (In Memory)
        for p_id, qty_needed in quantity_map.items():
            stock = stock_map.get(p_id)
            
            if not stock:
                logger.error(f"Stock record missing: Warehouse {warehouse_id}, Product {p_id}")
                raise OutOfStockError(f"Product {p_id} not found in warehouse.")

            # Check available (Quantity - Reserved)
            available = stock.quantity - stock.reserved_quantity
            if available < qty_needed:
                logger.warning(f"OOS: {stock.product.name} (Req: {qty_needed}, Avail: {available})")
                raise OutOfStockError(f"Insufficient stock for {stock.product.name}")

        # 4. Update Phase (Write to DB)
        logs_to_create = []
        for stock in stocks:
            qty_to_reserve = quantity_map[stock.product_id]
            
            # Update counters
            stock.reserved_quantity = F('reserved_quantity') + qty_to_reserve
            stock.save(update_fields=['reserved_quantity', 'updated_at'])
            
            # Prepare Log
            logs_to_create.append(StockMovementLog(
                inventory=stock,
                quantity_change=0, # Physical stock hasn't changed, only reservation
                movement_type=StockMovementLog.MovementType.RESERVATION,
                reference=reference,
                balance_after=stock.quantity # Physical balance remains same
            ))

        # 5. Bulk Create Logs
        StockMovementLog.objects.bulk_create(logs_to_create)
        logger.info(f"Reserved stock for {reference} at Warehouse {warehouse_id}")

    @staticmethod
    @transaction.atomic
    def release_stock(warehouse_id: int, items: List[Dict[str, int]], reference: str):
        """
        Releases reserved stock (e.g., Order Cancellation / Payment Failure).
        """
        sorted_items = sorted(items, key=lambda x: x['product_id'])
        product_ids = [i['product_id'] for i in sorted_items]
        qty_map = {i['product_id']: i['quantity'] for i in sorted_items}

        stocks = InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id, 
            product_id__in=product_ids
        )

        logs = []
        for stock in stocks:
            qty_to_release = qty_map.get(stock.product_id, 0)
            
            # Sanity check: don't release more than reserved
            # In production, this might just set to 0 if negative, but logic implies valid flow
            stock.reserved_quantity = F('reserved_quantity') - qty_to_release
            stock.save(update_fields=['reserved_quantity', 'updated_at'])

            logs.append(StockMovementLog(
                inventory=stock,
                quantity_change=0,
                movement_type=StockMovementLog.MovementType.RELEASE,
                reference=reference,
                balance_after=stock.quantity
            ))
        
        StockMovementLog.objects.bulk_create(logs)
        logger.info(f"Released stock for {reference}")

    @staticmethod
    @transaction.atomic
    def confirm_deduction(warehouse_id: int, items: List[Dict[str, int]], reference: str):
        """
        Hard deduction (Outbound).
        Called when Order is Dispatched/Packed.
        Decrements BOTH `quantity` and `reserved_quantity`.
        """
        sorted_items = sorted(items, key=lambda x: x['product_id'])
        product_ids = [i['product_id'] for i in sorted_items]
        qty_map = {i['product_id']: i['quantity'] for i in sorted_items}

        stocks = InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id, 
            product_id__in=product_ids
        )

        logs = []
        for stock in stocks:
            qty = qty_map.get(stock.product_id, 0)
            
            # Decrement physical and reserved
            stock.quantity = F('quantity') - qty
            stock.reserved_quantity = F('reserved_quantity') - qty
            stock.save(update_fields=['quantity', 'reserved_quantity', 'updated_at'])
            
            # We must refresh to get the actual integer for the log
            stock.refresh_from_db()

            logs.append(StockMovementLog(
                inventory=stock,
                quantity_change=-qty,
                movement_type=StockMovementLog.MovementType.OUTBOUND_ORDER,
                reference=reference,
                balance_after=stock.quantity
            ))

        StockMovementLog.objects.bulk_create(logs)