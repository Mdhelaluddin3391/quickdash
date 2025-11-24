# apps/inventory/management/commands/reconcile_inventory.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from apps.warehouse.models import BinInventory, Warehouse
from apps.inventory.models import InventoryStock, SKU

class Command(BaseCommand):
    help = "Reconciles InventoryStock (Logical) with BinInventory (Physical)"

    def handle(self, *args, **options):
        warehouses = Warehouse.objects.filter(is_active=True)
        
        for wh in warehouses:
            self.stdout.write(f"Checking Warehouse: {wh.code}")
            
            # Get all SKUs in this warehouse
            skus_in_bins = BinInventory.objects.filter(
                bin__zone__warehouse=wh
            ).values_list('sku', flat=True).distinct()

            for sku_id in skus_in_bins:
                # 1. Calculate Physical Totals
                totals = BinInventory.objects.filter(
                    bin__zone__warehouse=wh, 
                    sku_id=sku_id
                ).aggregate(
                    total_qty=Sum('qty'),
                    total_reserved=Sum('reserved_qty')
                )
                
                phy_qty = totals['total_qty'] or 0
                phy_reserved = totals['total_reserved'] or 0
                phy_available = max(0, phy_qty - phy_reserved)

                # 2. Compare with Logical Stock
                stock, _ = InventoryStock.objects.get_or_create(
                    warehouse=wh,
                    sku_id=sku_id,
                    defaults={'available_qty': 0, 'reserved_qty': 0}
                )

                if stock.available_qty != phy_available or stock.reserved_qty != phy_reserved:
                    self.stdout.write(
                        self.style.WARNING(
                            f"MISMATCH SKU {sku_id}: "
                            f"Logical(Avl={stock.available_qty}, Res={stock.reserved_qty}) != "
                            f"Physical(Avl={phy_available}, Res={phy_reserved})"
                        )
                    )
                    # Auto-fix
                    stock.available_qty = phy_available
                    stock.reserved_qty = phy_reserved
                    stock.save()
                    self.stdout.write(self.style.SUCCESS("FIXED"))
                else:
                    # self.stdout.write(f"SKU {sku_id} OK")
                    pass