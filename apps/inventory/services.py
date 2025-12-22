import logging
from typing import List, Dict
from django.db import transaction
from django.db.models import F
from apps.utils.exceptions import BusinessLogicException

from .models import InventoryStock, StockMovementLog

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Core Logic for Inventory Management.
    ALL stock changes must pass through here.
    """

    @staticmethod
    @transaction.atomic
    def bulk_lock_and_validate(
        warehouse_id: str,
        items: List[Dict[str, int]],
    ) -> Dict[str, InventoryStock]:
        """
        Locks inventory rows in deterministic order to prevent deadlocks.
        """
        # 1. Sort by Product ID to ensure lock ordering
        sorted_items = sorted(items, key=lambda x: str(x["product_id"]))
        product_ids = [i["product_id"] for i in sorted_items]
        
        # 2. Select For Update (Pessimistic Lock)
        stocks = (
            InventoryStock.objects
            .select_for_update()
            .filter(warehouse_id=warehouse_id, product_id__in=product_ids)
        )
        
        stock_map = {str(s.product_id): s for s in stocks}
        
        # 3. Validation Loop
        for item in sorted_items:
            pid = str(item["product_id"])
            qty_needed = item["quantity"]
            
            if pid not in stock_map:
                raise BusinessLogicException(f"Product {pid} not found in warehouse.")
            
            stock = stock_map[pid]
            if stock.available_quantity < qty_needed:
                raise BusinessLogicException(
                    f"Insufficient stock for {stock.product.sku_code}. "
                    f"Required: {qty_needed}, Available: {stock.available_quantity}"
                )
        
        return stock_map

    @staticmethod
    @transaction.atomic
    def reserve_stock(warehouse_id: str, items: List[Dict[str, int]], reference: str):
        """
        Locks stock and increments 'reserved_quantity'.
        """
        stocks = InventoryService.bulk_lock_and_validate(warehouse_id, items)
        logs = []

        for item in items:
            pid = str(item["product_id"])
            qty = item["quantity"]
            stock = stocks[pid]

            stock.reserved_quantity = F("reserved_quantity") + qty
            stock.save(update_fields=["reserved_quantity", "updated_at"])
            
            # Refresh for log snapshot
            stock.refresh_from_db()

            logs.append(StockMovementLog(
                inventory=stock,
                quantity_change=0, # Reservation doesn't change physical stock
                movement_type=StockMovementLog.MovementType.RESERVATION,
                reference=reference,
                balance_after=stock.quantity
            ))

        StockMovementLog.objects.bulk_create(logs)

    @staticmethod
    @transaction.atomic
    def release_stock(warehouse_id: str, items: List[Dict[str, int]], reference: str):
        """
        Reverses reservation (e.g., Order Cancellation).
        """
        # Lock rows first
        sorted_items = sorted(items, key=lambda x: str(x["product_id"]))
        product_ids = [i["product_id"] for i in sorted_items]
        
        stocks = InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id, product_id__in=product_ids
        )
        stock_map = {str(s.product_id): s for s in stocks}
        logs = []

        for item in sorted_items:
            pid = str(item["product_id"])
            qty = item["quantity"]
            
            if pid in stock_map:
                stock = stock_map[pid]
                stock.reserved_quantity = F("reserved_quantity") - qty
                stock.save(update_fields=["reserved_quantity", "updated_at"])
                stock.refresh_from_db()

                logs.append(StockMovementLog(
                    inventory=stock,
                    quantity_change=0,
                    movement_type=StockMovementLog.MovementType.RELEASE,
                    reference=reference,
                    balance_after=stock.quantity
                ))

        StockMovementLog.objects.bulk_create(logs)

    @staticmethod
    @transaction.atomic
    def confirm_deduction(warehouse_id: str, items: List[Dict[str, int]], reference: str):
        """
        Hard deduction (Physical stock leaves warehouse).
        Decreases BOTH quantity and reserved_quantity.
        """
        sorted_items = sorted(items, key=lambda x: str(x["product_id"]))
        product_ids = [i["product_id"] for i in sorted_items]
        
        stocks = InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id, product_id__in=product_ids
        )
        stock_map = {str(s.product_id): s for s in stocks}
        logs = []

        for item in sorted_items:
            pid = str(item["product_id"])
            qty = item["quantity"]
            
            if pid in stock_map:
                stock = stock_map[pid]
                stock.quantity = F("quantity") - qty
                stock.reserved_quantity = F("reserved_quantity") - qty
                stock.save(update_fields=["quantity", "reserved_quantity", "updated_at"])
                stock.refresh_from_db()

                logs.append(StockMovementLog(
                    inventory=stock,
                    quantity_change=-qty,
                    movement_type=StockMovementLog.MovementType.OUTBOUND_ORDER,
                    reference=reference,
                    balance_after=stock.quantity
                ))

        StockMovementLog.objects.bulk_create(logs)

    @staticmethod
    @transaction.atomic
    def manual_adjustment(warehouse_id: str, product_id: str, delta_qty: int, user, reason: str):
        """
        For Cycle Counts / Audits.
        """
        try:
            stock = InventoryStock.objects.select_for_update().get(
                warehouse_id=warehouse_id, product_id=product_id
            )
        except InventoryStock.DoesNotExist:
            raise BusinessLogicException("Stock record not found.")

        stock.quantity = F("quantity") + delta_qty
        stock.save(update_fields=["quantity", "updated_at"])
        stock.refresh_from_db()

        StockMovementLog.objects.create(
            inventory=stock,
            quantity_change=delta_qty,
            movement_type=StockMovementLog.MovementType.ADJUSTMENT,
            reference=f"MANUAL: {reason}",
            balance_after=stock.quantity,
            created_by=user
        )
        return stock

    @staticmethod
    def check_high_velocity_stock(product_id: str, qty: int):
        """
        [SCALABILITY FIX]
        Optimistic check in Redis before hitting DB lock.
        Use this for 'Hot SKUs' to prevent DB pile-up.
        """
        cache_key = f"stock_cache:{product_id}"
        cached_val = cache.get(cache_key)
        
        # If cache exists and is insufficient, fail fast
        if cached_val is not None and int(cached_val) < qty:
             raise BusinessLogicException("Out of stock (Fast Path)")
        
        return True


    @staticmethod
    def check_and_reserve_high_velocity(product_id: str, qty: int):
        """
        [SCALABILITY] Uses Redis Atomic Decrement for hot items.
        Returns True if stock was successfully reserved in Redis.
        """
        from django.core.cache import cache
        
        cache_key = f"stock_cache:{product_id}"
        
        # Lua Script ensures atomicity: Check if key exists -> Check value -> Decrement
        # Returns: New Value if success, -1 if missing/insufficient
        lua_script = """
        if redis.call('exists', KEYS[1]) == 1 then
            local curr = tonumber(redis.call('get', KEYS[1]))
            local req = tonumber(ARGV[1])
            if curr >= req then
                return redis.call('decrby', KEYS[1], req)
            else
                return -2 -- Insufficient
            end
        else
            return -1 -- Key missing (Fall back to DB)
        end
        """
        
        # We need raw redis client for Lua
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        try:
            result = redis_conn.eval(lua_script, 1, cache_key, qty)
            
            if result == -2:
                raise BusinessLogicException("Out of stock (Fast Path)")
            
            if result == -1:
                # Cache miss: We allow it to proceed to DB lock, 
                # OR we could force a cache warm-up here.
                # For safety, we return True to let DB handle it.
                return True
                
            return True
            
        except Exception as e:
            # If Redis fails, FAIL OPEN (Let DB handle it) to prevent downtime
            logger.warning(f"Redis Error for {product_id}: {e}")
            return True

    