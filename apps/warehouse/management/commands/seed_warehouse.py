from django.core.management.base import BaseCommand
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin
from apps.inventory.models import SKU, BinInventory, InventoryStock
import random

class Command(BaseCommand):
    help = "Seed a warehouse with zones/aisles/shelves/bins and random inventory"

    def handle(self, *args, **options):
        w, _ = Warehouse.objects.get_or_create(code='W1', defaults={'name':'Main Warehouse'})
        z, _ = Zone.objects.get_or_create(warehouse=w, code='DRY', defaults={'name':'Dry Goods'})
        for aidx in range(1,4):
            a, _ = Aisle.objects.get_or_create(zone=z, code=f'A{aidx}')
            for sidx in range(1,6):
                sh, _ = Shelf.objects.get_or_create(aisle=a, code=f'S{sidx}')
                for bidx in range(1,11):
                    bin_code = f'B{bidx:02d}'
                    b, created = Bin.objects.get_or_create(shelf=sh, code=bin_code)
        # create some SKUs
        skus = []
        for i in range(1,11):
            sku_code = f'SKU{i:03d}'
            sku, _ = SKU.objects.get_or_create(sku_code=sku_code, defaults={'name':f'Item {i}','unit':'pcs'})
            skus.append(sku)
        # populate bin inventories random
        bins = Bin.objects.all()[:200]
        for b in bins:
            for sku in random.sample(skus, k=3):
                qty = random.randint(10, 200)
                bi, _ = BinInventory.objects.get_or_create(bin=b, sku=sku, defaults={'qty':qty})
                # update warehouse stock
                stock, _ = InventoryStock.objects.get_or_create(warehouse=w, sku=sku, defaults={'available_qty':0})
                stock.available_qty += qty
                stock.save()
        self.stdout.write(self.style.SUCCESS('Seed complete'))
