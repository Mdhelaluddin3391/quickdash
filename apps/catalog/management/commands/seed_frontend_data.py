import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.utils.text import slugify

# Models Import
from apps.catalog.models import Category, Brand, SKU, Banner, FlashSale
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin, BinInventory
from apps.inventory.models import InventoryStock

class Command(BaseCommand):
    help = "Seeds Bulk Data: 10+ Categories, Sub-cats, and 500+ Products"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting BULK Data Seeding...")

        # ---------------------------------------------------------
        # 1. SETUP WAREHOUSE & BRANDS
        # ---------------------------------------------------------
        wh, _ = Warehouse.objects.get_or_create(
            code="WH-MAIN",
            defaults={"name": "Main Fulfillment Center", "address": "Tech Park, Bangalore", "is_active": True, "location": "POINT(77.5946 12.9716)"}
        )
        
        # Bins Setup
        zone, _ = Zone.objects.get_or_create(warehouse=wh, code="Z1", name="General")
        aisle, _ = Aisle.objects.get_or_create(zone=zone, code="A1")
        shelf, _ = Shelf.objects.get_or_create(aisle=aisle, code="S1")
        
        # [FIX] Use update_or_create instead of get_or_create based on unique bin_code
        # This handles cases where B-001 exists linked to an old shelf/warehouse
        bin_obj, _ = Bin.objects.update_or_create(
            bin_code="B-001",
            defaults={'shelf': shelf, 'capacity': 1000.0}
        )

        # Brands List
        brand_names = [
            "Amul", "Nestle", "Britannia", "Tata", "Fortune", "Aashirvaad", 
            "Cadbury", "Lays", "Haldiram", "Himalaya", "Pampers", "Dettol", 
            "Surf Excel", "Vim", "Coca-Cola", "Pepsi", "QuickDash Fresh"
        ]
        brands = []
        for b in brand_names:
            brand, _ = Brand.objects.get_or_create(name=b, defaults={'slug': slugify(b), 'is_active': True})
            brands.append(brand)

        # ---------------------------------------------------------
        # 2. MASTER DATA STRUCTURE (Nested Categories)
        # ---------------------------------------------------------
        
        CATALOG_DATA = {
            "Fruits & Vegetables": {
                "Fresh Vegetables": ["Potato", "Onion", "Tomato", "Chilli", "Lemon", "Ginger", "Garlic", "Carrot", "Capsicum", "Cabbage"],
                "Fresh Fruits": ["Apple", "Banana", "Orange", "Grapes", "Mango", "Papaya", "Watermelon", "Kiwi"],
                "Exotic & Organic": { 
                    "Exotic Veggies": ["Broccoli", "Zucchini", "Red Cabbage", "Mushroom", "Baby Corn"],
                    "Organic Picks": ["Organic Tomato", "Organic Spinach", "Organic Potato"]
                }
            },
            "Dairy, Bread & Eggs": {
                "Milk & Curd": ["Toned Milk", "Full Cream Milk", "Curd Pouch", "Greek Yogurt", "Buttermilk"],
                "Paneer & Butter": ["Fresh Paneer", "Salted Butter", "Unsalted Butter", "Cheese Slices", "Cheese Cubes"],
                "Bread & Eggs": ["White Bread", "Brown Bread", "Multigrain Bread", "Farm Eggs 6pcs", "Farm Eggs 12pcs", "Bun"]
            },
            "Atta, Rice & Dal": {
                "Atta & Flours": ["Chakki Atta", "Maida", "Sooji", "Besan", "Rice Flour", "Multigrain Atta"],
                "Rice & Rice Products": ["Basmati Rice", "Sona Masoori", "Poha", "Idli Rice", "Brown Rice"],
                "Dals & Pulses": ["Toor Dal", "Moong Dal", "Chana Dal", "Urad Dal", "Masoor Dal", "Rajma", "Kabuli Chana"]
            },
            "Masala, Oil & More": {
                "Edible Oils": ["Sunflower Oil", "Mustard Oil", "Ghee", "Olive Oil", "Groundnut Oil"],
                "Masalas & Spices": ["Turmeric Powder", "Chilli Powder", "Coriander Powder", "Garam Masala", "Jeera", "Mustard Seeds"],
                "Salt, Sugar & Jaggery": ["Iodized Salt", "Sugar", "Jaggery Cubes", "Rock Salt", "Brown Sugar"]
            },
            "Snacks & Munchies": {
                "Biscuits & Cookies": ["Marie Gold", "Good Day", "Oreo", "Digestive", "Cream Biscuit", "Rusks"],
                "Chips & Namkeen": ["Potato Chips", "Nachos", "Bhujia", "Mixture", "Peanuts", "Popcorn"],
                "Chocolates & Candies": ["Dairy Milk", "KitKat", "5 Star", "Gems", "Jelly Bears", "Lollipops"]
            },
            "Cold Drinks & Juices": {
                "Soft Drinks": ["Cola", "Orange Soda", "Lemon Drink", "Jeera Soda", "Ginger Ale"],
                "Juices & Energy": ["Mango Juice", "Mixed Fruit Juice", "Apple Juice", "Energy Drink", "Ice Tea"],
                "Water & Soda": ["Mineral Water 1L", "Mineral Water 500ml", "Club Soda", "Tonic Water"]
            },
            "Tea, Coffee & Health": {
                "Tea": ["Premium Tea", "Green Tea", "Ginger Tea", "Masala Tea Bags"],
                "Coffee": ["Instant Coffee", "Filter Coffee", "Coffee Beans", "Cappuccino Mix"],
                "Health Drinks": ["Chocolate Health Drink", "Malt Drink", "Protein Powder", "Glucose Powder"]
            },
            "Instant & Frozen Food": {
                "Noodles & Pasta": ["Instant Noodles", "Hakka Noodles", "Penne Pasta", "Macaroni", "Cup Noodles"],
                "Frozen Food": ["Frozen Peas", "French Fries", "Frozen Corn", "Veg Nuggets", "Chicken Nuggets"],
                "Ready to Eat": ["Ready Upma", "Ready Poha", "Instant Soup", "Dal Makhani Pack"]
            },
            "Personal Care": {
                "Bath & Body": ["Soap Bar", "Body Wash", "Hand Wash", "Shower Gel"],
                "Hair Care": ["Shampoo", "Conditioner", "Hair Oil", "Hair Color"],
                "Skin & Face": ["Face Wash", "Moisturizer", "Sunscreen", "Face Cream", "Lip Balm"],
                "Oral Care": ["Toothpaste", "Toothbrush", "Mouthwash"]
            },
            "Home & Cleaning": {
                "Detergents": ["Washing Powder", "Liquid Detergent", "Fabric Conditioner"],
                "Utensil Cleaners": ["Dish Wash Bar", "Dish Wash Liquid", "Steel Scrubber", "Sponge Wipe"],
                "Floor & Toilet": ["Floor Cleaner", "Toilet Cleaner", "Bathroom Cleaner", "Glass Cleaner"]
            },
            "Baby Care": {
                "Diapers & Wipes": ["Diapers S", "Diapers M", "Diapers L", "Diapers XL", "Baby Wipes"],
                "Baby Food": ["Apple Puree", "Cereal Mix", "Baby Biscuits"],
                "Baby Skin & Bath": ["Baby Oil", "Baby Soap", "Baby Shampoo", "Baby Powder", "Rash Cream"]
            }
        }

        # ---------------------------------------------------------
        # 3. HELPER TO CREATE PRODUCTS
        # ---------------------------------------------------------
        def create_products_for_category(cat_obj, brand_obj, item_list, count_needed=50):
            # Variants to multiply items
            variants = ["500g", "1kg", "2kg", "Pack of 2", "Small", "Large", "Family Pack"]
            
            created_count = 0
            
            # Loop until we satisfy the count
            while created_count < count_needed:
                for item_name in item_list:
                    if created_count >= count_needed: break
                    
                    variant = random.choice(variants)
                    full_name = f"{item_name} {variant}"
                    # Unique SKU Code Logic
                    sku_code = f"{slugify(item_name).upper()}-{random.randint(10000, 99999)}-{created_count}"
                    
                    price = random.randint(20, 800)
                    
                    sku, _ = SKU.objects.get_or_create(
                        name=full_name,
                        defaults={
                            "sku_code": sku_code,
                            "category": cat_obj,
                            "brand": brand_obj,
                            "unit": "pack",
                            "sale_price": Decimal(price),
                            "cost_price": Decimal(price * 0.8),
                            "is_active": True,
                            "image_url": f"https://placehold.co/400x400/png?text={item_name.replace(' ', '+')}"
                        }
                    )
                    
                    # Stock logic
                    BinInventory.objects.update_or_create(bin=bin_obj, sku=sku, defaults={"qty": 100, "reserved_qty": 0})
                    InventoryStock.objects.update_or_create(warehouse=wh, sku=sku, defaults={"available_qty": 100, "reserved_qty": 0})
                    
                    created_count += 1

        # ---------------------------------------------------------
        # 4. MAIN LOOP
        # ---------------------------------------------------------
        
        for main_cat_name, sub_data in CATALOG_DATA.items():
            self.stdout.write(f"📂 Processing: {main_cat_name}")
            
            # Create Main Category
            main_cat, _ = Category.objects.get_or_create(
                name=main_cat_name,
                defaults={"slug": slugify(main_cat_name), "is_active": True, "sort_order": random.randint(1,10)}
            )

            for sub_key, sub_val in sub_data.items():
                # Level 2: Sub Category
                sub_cat, _ = Category.objects.get_or_create(
                    name=sub_key,
                    parent=main_cat,
                    defaults={"slug": slugify(f"{main_cat_name} {sub_key}"), "is_active": True}
                )

                if isinstance(sub_val, list):
                    create_products_for_category(sub_cat, random.choice(brands), sub_val, count_needed=20)
                
                elif isinstance(sub_val, dict):
                    # Level 3: Sub-Sub Category
                    for sub_sub_key, items_list in sub_val.items():
                        sub_sub_cat, _ = Category.objects.get_or_create(
                            name=sub_sub_key,
                            parent=sub_cat,
                            defaults={"slug": slugify(f"{sub_key} {sub_sub_key}"), "is_active": True}
                        )
                        create_products_for_category(sub_sub_cat, random.choice(brands), items_list, count_needed=15)

        # ---------------------------------------------------------
        # 5. BANNERS & FLASH SALES
        # ---------------------------------------------------------
        self.stdout.write("🎨 Creating Banners & Sales...")
        Banner.objects.all().delete()
        FlashSale.objects.all().delete()

        # Hero Banners
        banners = [
            ("Super Grocery Sale", "HERO", "linear-gradient(135deg, #FF9966 0%, #FF5E62 100%)", "/category.html"),
            ("Fresh Veggies @ 50% Off", "HERO", "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)", "/category.html"),
            ("Summer Cool Drinks", "HERO", "linear-gradient(135deg, #56CCF2 0%, #2F80ED 100%)", "/category.html"),
            ("Snack Attack", "MID", "linear-gradient(135deg, #fceabb 0%, #f8b500 100%)", "/category.html"),
        ]
        
        for idx, b in enumerate(banners):
            Banner.objects.create(
                title=b[0], position=b[1], bg_gradient=b[2], target_url=b[3], 
                image_url="https://cdn-icons-png.flaticon.com/512/3081/3081559.png",
                is_active=True, sort_order=idx
            )

        # Flash Sales
        all_skus = list(SKU.objects.all()[:100])
        if all_skus:
            for _ in range(5):
                sku = random.choice(all_skus)
                FlashSale.objects.create(
                    sku=sku,
                    discounted_price=sku.sale_price * Decimal("0.5"),
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(days=2),
                    total_quantity=50,
                    sold_quantity=random.randint(2, 40),
                    is_active=True
                )

        self.stdout.write(self.style.SUCCESS("✅ SUCCESS: Bulk Data Seeded!"))