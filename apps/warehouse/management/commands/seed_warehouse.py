from django.core.management.base import BaseCommand
from django.db import transaction
import random

# Correct Imports
from apps.catalog.models import SKU
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin, BinInventory
from apps.inventory.models import InventoryStock

class Command(BaseCommand):
    help = "Seed a warehouse with zones/aisles/shelves/bins and random inventory"

    def handle(self, *args, **options):
        self.stdout.write("Seeding warehouse data...")

        # 1. Warehouse Setup
        w, _ = Warehouse.objects.get_or_create(
            code='W1', 
            defaults={'name':'Main Warehouse', 'address': '123 Main St', 'is_active': True}
        )
        
        z, _ = Zone.objects.get_or_create(warehouse=w, code='DRY', defaults={'name':'Dry Goods'})
        
        # Create Aisles, Shelves, Bins
        for aidx in range(1, 4): # A1, A2, A3
            a, _ = Aisle.objects.get_or_create(zone=z, code=f'A{aidx}')
            for sidx in range(1, 6): # S1..S5
                sh, _ = Shelf.objects.get_or_create(aisle=a, code=f'S{sidx}')
                for bidx in range(1, 11): # B01..B10
                    bin_code = f'{a.code}-{sh.code}-B{bidx:02d}'
                    # Use get_or_create safely with unique constraint
                    Bin.objects.get_or_create(shelf=sh, bin_code=bin_code)

        self.stdout.write("Warehouse structure created.")

        # 2. Create Dummy SKUs
        skus = []
        for i in range(1, 11):
            sku_code = f'SKU{i:03d}'
            sku, _ = SKU.objects.get_or_create(
                sku_code=sku_code, 
                defaults={
                    'name': f'Item {i}',
                    'unit': 'pcs',
                    'sale_price': 100.00,
                    'is_active': True
                }
            )
            skus.append(sku)
        
        self.stdout.write(f"Created {len(skus)} SKUs.")

        # 3. Populate Inventory
        # Use atomic transaction for safety
        with transaction.atomic():
            bins = Bin.objects.filter(shelf__aisle__zone__warehouse=w)[:50] # Seed first 50 bins
            
            for b in bins:
                # Har bin mein 1-3 random SKUs daalo
                selected_skus = random.sample(skus, k=random.randint(1, 3))
                
                for sku in selected_skus:
                    qty = random.randint(10, 200)
                    
                    # Physical Stock (Bin)
                    BinInventory.objects.get_or_create(
                        bin=b, 
                        sku=sku, 
                        defaults={'qty': qty, 'reserved_qty': 0}
                    )

                    # Logical Stock (Central Inventory) - Aggregate update
                    stock, _ = InventoryStock.objects.get_or_create(
                        warehouse=w, 
                        sku=sku, 
                        defaults={'available_qty': 0, 'reserved_qty': 0}
                    )
                    stock.available_qty += qty
                    stock.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded warehouse W1 with inventory!'))