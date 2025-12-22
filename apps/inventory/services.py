import logging
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.inventory.models import InventoryItem
from apps.catalog.models import Product

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Service for managing inventory levels, stock allocation, and reconciliation.
    Ensures atomic updates to prevent race conditions.
    """

    @staticmethod
    def get_total_stock(product: Product) -> int:
        """Returns total available stock across all warehouses."""
        items = InventoryItem.objects.filter(product=product)
        return sum(item.quantity for item in items)

    @staticmethod
    @transaction.atomic
    def check_and_allocate_stock(product: Product, quantity: int, warehouse=None):
        """
        Checks if enough stock exists and reserves it.
        Uses select_for_update() to lock rows and prevent race conditions.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be positive.")

        # If a specific warehouse is requested, lock only that record
        if warehouse:
            inventory_qs = InventoryItem.objects.select_for_update().filter(
                product=product, warehouse=warehouse
            )
        else:
            # Otherwise, check all warehouses (simplified allocation strategy: First Match)
            inventory_qs = InventoryItem.objects.select_for_update().filter(
                product=product, quantity__gte=0
            ).order_by('-quantity')

        if not inventory_qs.exists():
            logger.warning(f"No inventory record found for product {product.id}")
            raise ValidationError(f"Product {product.name} is out of stock.")

        remaining_needed = quantity
        allocated_items = []

        # Greedy allocation logic
        for item in inventory_qs:
            if remaining_needed <= 0:
                break

            available = item.quantity - item.reserved_quantity
            
            if available <= 0:
                continue

            to_take = min(remaining_needed, available)
            
            # Update the record in memory
            item.reserved_quantity += to_take
            item.save()
            
            allocated_items.append(item)
            remaining_needed -= to_take

        if remaining_needed > 0:
            # Rollback is automatic due to transaction.atomic if we raise error here
            logger.info(f"Insufficient stock for {product.name}. Needed {quantity}, missing {remaining_needed}")
            raise ValidationError(f"Insufficient stock for {product.name}. Only {quantity - remaining_needed} available.")
        
        logger.info(f"Successfully allocated {quantity} of {product.name}")
        return True

    @staticmethod
    @transaction.atomic
    def release_stock(product: Product, quantity: int):
        """
        Releases reserved stock back to available pool (e.g. Order Cancellation).
        """
        # We need to find where the stock was reserved. 
        # For simplicity in this recovery phase, we release from items with reserved stock.
        inventory_items = InventoryItem.objects.select_for_update().filter(
            product=product, reserved_quantity__gt=0
        )

        remaining_to_release = quantity

        for item in inventory_items:
            if remaining_to_release <= 0:
                break

            to_release = min(remaining_to_release, item.reserved_quantity)
            item.reserved_quantity -= to_release
            item.save()
            remaining_to_release -= to_release

        if remaining_to_release > 0:
            logger.error(f"Could not fully release stock for {product.name}. Mismatch detected.")
            # We do NOT raise here to avoid blocking cancellation flows, but we log strictly.

    @staticmethod
    @transaction.atomic
    def confirm_shipment(product: Product, quantity: int):
        """
        Permanently removes stock from quantity and reserved_quantity (Order Fulfilled).
        """
        inventory_items = InventoryItem.objects.select_for_update().filter(
            product=product, reserved_quantity__gt=0
        )
        
        remaining = quantity
        for item in inventory_items:
            if remaining <= 0:
                break
            
            deduct = min(remaining, item.reserved_quantity)
            item.quantity -= deduct
            item.reserved_quantity -= deduct
            item.save()
            remaining -= deduct
            
        if remaining > 0:
            logger.critical(f"Shipment confirmed for {product.name} but reserved stock was missing!")