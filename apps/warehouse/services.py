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