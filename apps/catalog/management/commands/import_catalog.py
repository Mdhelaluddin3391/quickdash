# apps/catalog/management/commands/import_catalog.py
import csv
from django.core.management.base import BaseCommand
from apps.catalog.models import SKU, Category, Brand

class Command(BaseCommand):
    help = "Import SKUs from CSV: sku_code,name,category,brand,price"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                cat, _ = Category.objects.get_or_create(name=row['category'])
                brand, _ = Brand.objects.get_or_create(name=row['brand'])
                
                SKU.objects.update_or_create(
                    sku_code=row['sku_code'],
                    defaults={
                        'name': row['name'],
                        'category': cat,
                        'brand': brand,
                        'sale_price': row['price'],
                        'is_active': True
                    }
                )
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f"Imported {count} SKUs successfully."))