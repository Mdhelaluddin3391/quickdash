import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.catalog.models import Category, Brand, SKU

class Command(BaseCommand):
    help = 'Import Catalog from CSV'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to CSV file')

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                # FIX: Atomic
                with transaction.atomic():
                    for row in reader:
                        cat_name = row.get('category', '').strip()
                        brand_name = row.get('brand', '').strip()
                        sku_code = row.get('sku_code', '').strip()
                        name = row.get('name', '').strip()
                        price = row.get('price', '0')

                        if cat_name and sku_code and name:
                            category, _ = Category.objects.get_or_create(name=cat_name)
                            brand, _ = Brand.objects.get_or_create(name=brand_name) if brand_name else (None, False)

                            SKU.objects.update_or_create(
                                sku_code=sku_code,
                                defaults={
                                    'name': name,
                                    'category': category,
                                    'brand': brand,
                                    'sale_price': float(price),
                                    'is_active': True
                                }
                            )
                            count += 1
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {count} items.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {str(e)}'))