import random
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.catalog.models import SKU
from apps.warehouse.models import Warehouse, Bin, BinInventory
from apps.inventory.models import InventoryStock


class Command(BaseCommand):
    help = "Seed inventory stock for all SKUs across warehouses"

    def add_arguments(self, parser):
        parser.add_argument(
            '--qty',
            type=int,
            default=50,
            help='Default quantity per SKU per warehouse'
        )

    def handle(self, *args, **options):
        qty = options['qty']
        
        warehouses = Warehouse.objects.filter(is_active=True)
        if not warehouses.exists():
            self.stdout.write(self.style.ERROR("No active warehouses found"))
            return

        skus = SKU.objects.filter(is_active=True)
        if not skus.exists():
            self.stdout.write(self.style.ERROR("No active SKUs found"))
            return

        self.stdout.write(f"Seeding inventory for {skus.count()} SKUs across {warehouses.count()} warehouses...")

        with transaction.atomic():
            total_created = 0
            total_updated = 0

            for warehouse in warehouses:
                # Get bins for this warehouse
                bins = Bin.objects.filter(
                    shelf__aisle__zone__warehouse=warehouse
                )[:50]
                
                if not bins.exists():
                    self.stdout.write(
                        self.style.WARNING(f"No bins found for warehouse {warehouse.code}")
                    )
                    continue

                bin_list = list(bins)

                for sku in skus:
                    # Distribute SKU across 2-5 random bins
                    selected_bins = random.sample(
                        bin_list,
                        k=min(random.randint(2, 5), len(bin_list))
                    )
                    
                    total_bin_qty = 0
                    for bin_obj in selected_bins:
                        bin_qty = random.randint(20, 100)
                        total_bin_qty += bin_qty
                        
                        # Create/Update BinInventory
                        bin_inv, created = BinInventory.objects.get_or_create(
                            bin=bin_obj,
                            sku=sku,
                            defaults={'qty': bin_qty, 'reserved_qty': 0}
                        )
                        
                        if not created:
                            bin_inv.qty = bin_qty
                            bin_inv.reserved_qty = 0
                            bin_inv.save()
                        
                        if created:
                            total_created += 1
                        else:
                            total_updated += 1

                    # Create/Update InventoryStock (central aggregated inventory)
                    stock, created = InventoryStock.objects.get_or_create(
                        warehouse=warehouse,
                        sku=sku,
                        defaults={'available_qty': total_bin_qty, 'reserved_qty': 0}
                    )
                    
                    if not created:
                        stock.available_qty = total_bin_qty
                        stock.reserved_qty = 0
                        stock.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Inventory seeded successfully!\n"
                    f"   Created: {total_created} BinInventory records\n"
                    f"   Updated: {total_updated} BinInventory records"
                )
            )
