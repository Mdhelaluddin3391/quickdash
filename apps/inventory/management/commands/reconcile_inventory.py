from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from apps.warehouse.models import BinInventory, Warehouse
from apps.inventory.models import InventoryStock, InventoryHistory

class Command(BaseCommand):
    help = "Reconciles InventoryStock (Logical) with BinInventory (Physical)"

    def handle(self, *args, **options):
        self.stdout.write("Starting Inventory Reconciliation...")
        
        warehouses = Warehouse.objects.filter(is_active=True)
        fixed_count = 0
        
        for wh in warehouses:
            # 1. Get all SKUs present in this warehouse (Physical OR Logical)
            physical_skus = BinInventory.objects.filter(
                bin__zone__warehouse=wh
            ).values_list('sku_id', flat=True).distinct()
            
            logical_skus = InventoryStock.objects.filter(
                warehouse=wh
            ).values_list('sku_id', flat=True).distinct()
            
            all_sku_ids = set(list(physical_skus) + list(logical_skus))

            for sku_id in all_sku_ids:
                with transaction.atomic():
                    # Calculate Physical Totals
                    totals = BinInventory.objects.filter(
                        bin__zone__warehouse=wh, 
                        sku_id=sku_id
                    ).aggregate(
                        total_qty=Sum('qty'),
                        total_reserved=Sum('reserved_qty')
                    )
                    
                    phy_total = totals['total_qty'] or 0
                    phy_reserved = totals['total_reserved'] or 0
                    phy_available = max(0, phy_total - phy_reserved)

                    # Get Logical Record (Lock it)
                    stock, _ = InventoryStock.objects.select_for_update().get_or_create(
                        warehouse=wh,
                        sku_id=sku_id,
                        defaults={'available_qty': 0, 'reserved_qty': 0}
                    )

                    if stock.available_qty != phy_available or stock.reserved_qty != phy_reserved:
                        self.stdout.write(
                            self.style.WARNING(
                                f"MISMATCH {wh.code} SKU {sku_id} :: "
                                f"Logical(A:{stock.available_qty}, R:{stock.reserved_qty}) != "
                                f"Physical(A:{phy_available}, R:{phy_reserved})"
                            )
                        )
                        
                        # Fix it
                        old_avail = stock.available_qty
                        stock.available_qty = phy_available
                        stock.reserved_qty = phy_reserved
                        stock.save()
                        
                        # Log the manual fix
                        InventoryHistory.objects.create(
                            stock=stock,
                            warehouse=wh,
                            sku_id=sku_id,
                            delta_available=(phy_available - old_avail),
                            delta_reserved=0,
                            available_after=phy_available,
                            reserved_after=phy_reserved,
                            change_type="RECONCILIATION_FIX",
                            reference="SYSTEM_NIGHTLY"
                        )
                        fixed_count += 1

        self.stdout.write(self.style.SUCCESS(f"Reconciliation Complete. Fixed {fixed_count} discrepancies."))