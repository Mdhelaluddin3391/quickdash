from django.db import transaction
from django.core.exceptions import ValidationError
from .models import InventoryStock, StockTransaction
from apps.catalog.models import Product
from apps.warehouse.models import Warehouse

class InventoryService:
    
    @staticmethod
    def bulk_lock_and_validate(product_quantity_map, warehouse):
        """
        Acquires a PESSIMISTIC LOCK (select_for_update) on all inventory items 
        in the cart to prevent race conditions during checkout.
        
        Args:
            product_quantity_map (dict): {product_id: quantity_needed}
            warehouse (Warehouse): The warehouse to check against
            
        Returns:
            dict: Map of {product_id: InventoryStock_object}
            
        Raises:
            ValidationError: If any product is OOS or missing
        """
        product_ids = list(product_quantity_map.keys())
        
        # KEY ARCHITECTURAL FIX: select_for_update() locks these rows until the transaction ends.
        # This prevents other concurrent checkout requests from reading old 'available_quantity'.
        stocks = InventoryStock.objects.select_for_update().filter(
            warehouse=warehouse,
            product_id__in=product_ids
        )
        
        stock_map = {stock.product_id: stock for stock in stocks}
        
        # Validation Phase
        for product_id, quantity_needed in product_quantity_map.items():
            stock = stock_map.get(product_id)
            
            if not stock:
                raise ValidationError(f"Product ID {product_id} not found in warehouse {warehouse.name}")
                
            if stock.available_quantity < quantity_needed:
                raise ValidationError(f"Insufficient stock for {stock.product.name}. Available: {stock.available_quantity}, Requested: {quantity_needed}")
                
        return stock_map

    @staticmethod
    def check_stock_availability(product, quantity, warehouse):
        """
        Read-only check for UI/Cart validation. NOT safe for checkout.
        """
        try:
            stock = InventoryStock.objects.get(product=product, warehouse=warehouse)
            return stock.available_quantity >= quantity
        except InventoryStock.DoesNotExist:
            return False

    @staticmethod
    def reserve_stock(product, quantity, warehouse, reference=None):
        """
        Decrements available stock. Assumes lock is already held by caller if part of checkout.
        """
        # We fetch again (or use the locked object passed in refactor) - simplest compliance here:
        stock = InventoryStock.objects.get(product=product, warehouse=warehouse)
        
        if stock.available_quantity < quantity:
            raise ValidationError(f"Stock changed during processing for {product.name}")
            
        stock.available_quantity -= quantity
        stock.reserved_quantity += quantity
        stock.save()
        
        StockTransaction.objects.create(
            warehouse=warehouse,
            product=product,
            quantity=-quantity,
            transaction_type='RESERVE',
            reference=reference,
            balance_after=stock.quantity
        )

    @staticmethod
    def release_stock(product, quantity, warehouse, reference=None):
        try:
            stock = InventoryStock.objects.get(product=product, warehouse=warehouse)
            stock.reserved_quantity = max(0, stock.reserved_quantity - quantity)
            stock.available_quantity += quantity
            stock.save()
            
            StockTransaction.objects.create(
                warehouse=warehouse,
                product=product,
                quantity=quantity,
                transaction_type='RELEASE',
                reference=reference,
                balance_after=stock.quantity
            )
        except InventoryStock.DoesNotExist:
            pass  # Should handle error logging
            
    @staticmethod
    def confirm_stock_deduction(product, quantity, warehouse, reference=None):
        stock = InventoryStock.objects.get(product=product, warehouse=warehouse)
        stock.reserved_quantity = max(0, stock.reserved_quantity - quantity)
        stock.quantity -= quantity
        stock.save()
        
        StockTransaction.objects.create(
            warehouse=warehouse,
            product=product,
            quantity=-quantity,
            transaction_type='SALE',
            reference=reference,
            balance_after=stock.quantity
        )
        
    @staticmethod
    def sync_stock_from_warehouse(product, warehouse, total_physical_qty):
        """
        Syncs logical inventory with physical warehouse bin data.
        Called explicitly by WarehouseService.
        """
        stock, _ = InventoryStock.objects.get_or_create(
            product=product, 
            warehouse=warehouse,
            defaults={'quantity': 0, 'available_quantity': 0}
        )
        
        # If physical stock > current logical total (quantity), we add the difference
        # If physical stock < current logical total, we adjust down
        
        diff = total_physical_qty - stock.quantity
        
        if diff != 0:
            stock.quantity = total_physical_qty
            # We assume change affects available_quantity directly
            stock.available_quantity += diff
            stock.save()