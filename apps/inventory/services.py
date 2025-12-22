from django.db import transaction
from django.db.models import F
from .models import WarehouseInventory, StockMovementLog
from apps.utils.exceptions import BusinessLogicException

class InventoryService:
    @staticmethod
    def check_availability(warehouse_id, product_id, requested_qty):
        try:
            inventory = WarehouseInventory.objects.get(
                warehouse_id=warehouse_id, 
                product_id=product_id
            )
            return inventory.available_quantity >= requested_qty
        except WarehouseInventory.DoesNotExist:
            return False

    @staticmethod
    @transaction.atomic
    def reserve_stock(warehouse_id, product_id, qty, order_id):
        """
        Locks the row and reserves stock.
        CRITICAL: Must be atomic to prevent race conditions.
        """
        try:
            # select_for_update() locks the row until transaction commits
            inventory = WarehouseInventory.objects.select_for_update().get(
                warehouse_id=warehouse_id, 
                product_id=product_id
            )
            
            if inventory.available_quantity < qty:
                raise BusinessLogicException(f"Insufficient stock for product {product_id}")
            
            # Update using F expressions for safety
            inventory.reserved_quantity = F('reserved_quantity') + qty
            inventory.save()
            
            # We don't log movement yet, only reservation.
            return True
        except WarehouseInventory.DoesNotExist:
            raise BusinessLogicException("Product not available in this warehouse")

    @staticmethod
    @transaction.atomic
    def confirm_stock_deduction(warehouse_id, product_id, qty, order_id):
        """
        Called when payment is successful. Converts reservation to permanent deduction.
        """
        inventory = WarehouseInventory.objects.select_for_update().get(
            warehouse_id=warehouse_id, 
            product_id=product_id
        )
        
        # Release reservation and reduce actual quantity
        inventory.reserved_quantity = F('reserved_quantity') - qty
        inventory.quantity = F('quantity') - qty
        inventory.save()
        
        StockMovementLog.objects.create(
            inventory=inventory,
            quantity_change=-qty,
            movement_type='OUTBOUND',
            reference_id=str(order_id)
        )

    @staticmethod
    @transaction.atomic
    def release_reservation(warehouse_id, product_id, qty):
        """
        Called if payment fails or order timeout.
        """
        inventory = WarehouseInventory.objects.select_for_update().get(
            warehouse_id=warehouse_id, 
            product_id=product_id
        )
        inventory.reserved_quantity = F('reserved_quantity') - qty
        inventory.save()