# apps/catalog/management/commands/seed_frontend_data.py
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Category, Brand, SKU
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin, BinInventory
from apps.inventory.models import InventoryStock

class Command(BaseCommand):
    help = "Seeds 10 Categories and 150 Products for Frontend Testing"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Data Seeding...")

        # 1. Setup Base Warehouse (Required for products to be visible)
        wh, _ = Warehouse.objects.get_or_create(
            code="WH-TEST",
            defaults={
                "name": "Frontend Test Hub",
                "address": "123 Tech Park, Bangalore",
                "is_active": True, 
                "location": "POINT(77.5946 12.9716)"
            }
        )
        
        # Ensure Bin structure exists
        zone, _ = Zone.objects.get_or_create(warehouse=wh, code="Z1", name="General")
        aisle, _ = Aisle.objects.get_or_create(zone=zone, code="A1")
        shelf, _ = Shelf.objects.get_or_create(aisle=aisle, code="S1")
        bin_obj, _ = Bin.objects.get_or_create(shelf=shelf, bin_code="B-001")

        # 2. Define Data (10 Categories x 15 Items)
        DATA = {
            "Fresh Vegetables": [
                "Onion", "Potato", "Tomato", "Ginger", "Garlic", "Coriander", "Spinach", "Carrot", 
                "Cucumber", "Green Chilli", "Lemon", "Capsicum", "Cauliflower", "Cabbage", "Broccoli"
            ],
            "Fresh Fruits": [
                "Banana", "Apple", "Orange", "Grapes", "Watermelon", "Papaya", "Pomegranate", "Kiwi", 
                "Mango", "Pineapple", "Strawberry", "Guava", "Pear", "Muskmelon", "Dragon Fruit"
            ],
            "Dairy & Breakfast": [
                "Milk 500ml", "Curd 400g", "Paneer 200g", "Butter 100g", "Cheese Slices", "Bread White", 
                "Bread Brown", "Eggs 6pcs", "Yogurt", "Fresh Cream", "Soy Milk", "Oats 1kg", 
                "Corn Flakes", "Muesli", "Peanut Butter"
            ],
            "Snacks & Munchies": [
                "Potato Chips", "Nachos", "Popcorn", "Bhujia", "Peanuts", "Choco Pie", "Biscuits", 
                "Cookies", "Rusks", "Cup Noodles", "Instant Pasta", "Namkeen Mix", "Murukku", "Khakhra", "Chakli"
            ],
            "Cold Drinks": [
                "Cola Can", "Lemon Soda", "Orange Drink", "Energy Drink", "Ice Tea", "Cold Coffee", 
                "Mineral Water 1L", "Sparkling Water", "Mango Juice", "Apple Juice", "Mixed Fruit Juice", 
                "Tonic Water", "Ginger Ale", "Soda Water", "Coconut Water"
            ],
            "Chocolates & Ice Cream": [
                "Dairy Milk", "KitKat", "5 Star", "Dark Chocolate", "Milk Chocolate", "Choco Bar", 
                "Vanilla Tub", "Chocolate Tub", "Butterscotch Cone", "Kulfi", "Ice Cream Sandwich", 
                "Gummy Bears", "Jelly Beans", "Lollipops", "Mint Candy"
            ],
            "Staples & Atta": [
                "Atta 5kg", "Basmati Rice 1kg", "Toor Dal", "Moong Dal", "Chana Dal", "Urad Dal", 
                "Sugar 1kg", "Salt 1kg", "Sunflower Oil 1L", "Mustard Oil 1L", "Ghee 500ml", 
                "Poha", "Sooji", "Maida", "Besan"
            ],
            "Personal Care": [
                "Soap Bar", "Body Wash", "Shampoo", "Conditioner", "Face Wash", "Hand Wash", 
                "Toothpaste", "Toothbrush", "Deodorant", "Perfume", "Hair Oil", "Moisturizer", 
                "Sunscreen", "Lip Balm", "Shaving Cream"
            ],
            "Home & Cleaning": [
                "Detergent Powder", "Liquid Detergent", "Dish Wash Bar", "Dish Wash Liquid", 
                "Floor Cleaner", "Toilet Cleaner", "Glass Cleaner", "Air Freshener", "Garbage Bags", 
                "Paper Napkins", "Toilet Paper", "Kitchen Towel", "Scrub Pad", "Broom", "Mop"
            ],
            "Baby Care": [
                "Diapers S", "Diapers M", "Diapers L", "Baby Wipes", "Baby Powder", "Baby Oil", 
                "Baby Soap", "Baby Shampoo", "Baby Lotion", "Diaper Rash Cream", "Feeding Bottle", 
                "Baby Food 6m+", "Baby Cereal", "Teether", "Baby Bibs"
            ]
        }

        # 3. Create Brand
        brand, _ = Brand.objects.get_or_create(name="QuickDash Select", is_active=True)

        # 4. Generate Data
        count = 0
        for cat_name, items in DATA.items():
            # Create Category
            cat_slug = slugify(cat_name)
            category, _ = Category.objects.get_or_create(
                name=cat_name,
                defaults={
                    "slug": cat_slug, 
                    "is_active": True,
                    # Placeholder Icon
                    "icon_url": f"https://source.unsplash.com/100x100/?{cat_slug}"
                }
            )
            self.stdout.write(f"📁 Processing {cat_name}...")

            for item_name in items:
                sku_code = f"{slugify(item_name).upper()}-{random.randint(1000,9999)}"
                price = random.randint(20, 500)
                
                # Create SKU
                sku, created = SKU.objects.get_or_create(
                    name=item_name,
                    defaults={
                        "sku_code": sku_code,
                        "category": category,
                        "brand": brand,
                        "unit": "pack",
                        "sale_price": Decimal(price),
                        "cost_price": Decimal(price * 0.8),
                        "is_active": True,
                        "is_featured": random.choice([True, False]),
                        "image_url": "https://placehold.co/400x400/png" # Reliable placeholder
                    }
                )

                # Add Stock (Physical + Logical)
                BinInventory.objects.update_or_create(
                    bin=bin_obj, sku=sku,
                    defaults={"qty": 50, "reserved_qty": 0}
                )
                
                InventoryStock.objects.update_or_create(
                    warehouse=wh, sku=sku,
                    defaults={"available_qty": 50, "reserved_qty": 0}
                )
                count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Successfully seeded {count} products across 10 categories!"))