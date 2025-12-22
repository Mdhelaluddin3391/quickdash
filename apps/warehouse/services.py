from django.db import transaction
from django.db.models import Sum
from .models import BinInventory, Bin
from apps.inventory.services import InventoryService

class WarehouseService:
    
    @staticmethod
    def update_bin_inventory(warehouse, bin_code, sku, quantity, change_type='ADD'):
        """
        Updates physical bin inventory and explicitly syncs logical inventory.
        """
        with transaction.atomic():
            bin_obj = Bin.objects.get(warehouse=warehouse, code=bin_code)
            
            # Update Physical Inventory
            inventory, created = BinInventory.objects.get_or_create(
                bin=bin_obj,
                product__sku=sku,
                defaults={'quantity': 0}
            )
            
            if change_type == 'ADD':
                inventory.quantity += quantity
            elif change_type == 'REMOVE':
                if inventory.quantity < quantity:
                    raise ValueError("Insufficient quantity in bin")
                inventory.quantity -= quantity
            
            inventory.save()
            
            # --- CRITICAL FIX: EXPLICIT SYNC ---
            # Replaces the unstable signal/receiver pattern.
            # We calculate total physical stock for this SKU in this warehouse
            total_physical = BinInventory.objects.filter(
                bin__warehouse=warehouse,
                product__sku=sku
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Explicit call to Inventory Service
            InventoryService.sync_stock_from_warehouse(
                product=inventory.product,
                warehouse=warehouse,
                total_physical_qty=total_physical
            )
            
            return inventory


from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Bin, Stock

class PutawayService:
    @staticmethod
    def calculate_putaway_plan(sku, total_quantity, warehouse):
        """
        Distributes stock across multiple bins based on available capacity.
        Returns a list of (bin, quantity_to_add).
        """
        # Get all eligible bins for this SKU or Empty bins, sorted by current load (fill nearly full ones first or empty ones? 
        # Strategy: Fill mostly full bins first to clear aisles, then empty ones.)
        eligible_bins = Bin.objects.filter(
            warehouse=warehouse,
            is_active=True
        ).exclude(status='DAMAGED').order_by('-current_load')

        plan = []
        remaining_qty = total_quantity

        for bin in eligible_bins:
            if remaining_qty <= 0:
                break
            
            # Assuming Bin has a 'capacity' field and 'current_load' field
            available_space = bin.capacity - bin.current_load
            
            if available_space > 0:
                qty_to_fit = min(remaining_qty, available_space)
                plan.append((bin, qty_to_fit))
                remaining_qty -= qty_to_fit

        if remaining_qty > 0:
            raise ValidationError(f"Warehouse Capacity Full! Cannot store {remaining_qty} items of {sku}.")
            
        return plan

    @staticmethod
    @transaction.atomic
    def execute_grn(sku, total_quantity, warehouse):
        plan = PutawayService.calculate_putaway_plan(sku, total_quantity, warehouse)
        
        for target_bin, qty in plan:
            # Create or Update Stock
            stock, created = Stock.objects.select_for_update().get_or_create(
                bin=target_bin,
                sku=sku,
                defaults={'quantity': 0}
            )
            stock.quantity += qty
            stock.save()
            
            # Update Bin Load
            target_bin.current_load += qty
            target_bin.save()
            
        return plan