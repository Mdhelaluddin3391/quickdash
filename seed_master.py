# seed_master.py
import os
import django
import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
from django.db import transaction

# 1. Django Setup (Zaroori hai kyunki ye root mein hai)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Models Import
from apps.catalog.models import Category, Brand, SKU, Banner, FlashSale
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin, BinInventory
from apps.inventory.models import InventoryStock

def run_seed():
    print("🚀 Starting MASTER Data Seeding (Bulk Mode)...")

    with transaction.atomic():
        # ==========================================
        # 1. WAREHOUSE SETUP (Infrastructure)
        # ==========================================
        print("🏗️  Setting up Warehouse & Bins...")
        
        # FIX: Matches apps/warehouse/models.py structure
        # Removed 'address' and 'location', added 'latitude'/'longitude'
        wh, _ = Warehouse.objects.get_or_create(
            code="WH-MAIN",
            defaults={
                "name": "Central Fulfillment Center", 
                "latitude": 12.9716,  # Bangalore Lat
                "longitude": 77.5946, # Bangalore Lng
                "service_radius_km": 10000000.0,
                "is_active": True, 
            }
        )
        
        # Structure: Zone -> Aisle -> Shelf -> Bin
        zone, _ = Zone.objects.get_or_create(warehouse=wh, code="Z1", defaults={"name": "General Storage"})
        
        # Create 5 Aisles, 5 Shelves per Aisle, 10 Bins per Shelf = 250 Bins
        all_bins = []
        for a_idx in range(1, 6): # A1..A5
            aisle, _ = Aisle.objects.get_or_create(zone=zone, code=f"A{a_idx}")
            for s_idx in range(1, 6): # S1..S5
                shelf, _ = Shelf.objects.get_or_create(aisle=aisle, code=f"S{s_idx}")
                for b_idx in range(1, 11): # B01..B10
                    bin_code = f"{aisle.code}-{shelf.code}-B{b_idx:02d}"
                    bin_obj, _ = Bin.objects.get_or_create(
                        shelf=shelf, 
                        bin_code=bin_code,
                        defaults={'capacity': 5000.0}
                    )
                    all_bins.append(bin_obj)
        
        print(f"    ✅ Created {len(all_bins)} Bins in Warehouse.")

        # ==========================================
        # 2. CATALOG SETUP (Brands & Categories)
        # ==========================================
        print("📦 Setting up Brands & Categories...")
        
        # Brands
        brand_names = [
            "Amul", "Nestle", "Britannia", "Tata", "Fortune", "Aashirvaad", 
            "Cadbury", "Lays", "Haldiram", "Himalaya", "Pampers", "Dettol", 
            "Surf Excel", "Vim", "Coca-Cola", "Pepsi", "Samsung", "Sony", 
            "Nike", "Adidas", "Loreal", "Nivea", "Dove", "Colgate", "Oral-B",
            "QuickDash Fresh"
        ]
        brands = []
        for b in brand_names:
            brand, _ = Brand.objects.get_or_create(name=b, defaults={'slug': slugify(b), 'is_active': True})
            brands.append(brand)

        # Categories Logic
        CATALOG_DATA = {
            "Fruits & Vegetables": ["Potato", "Onion", "Tomato", "Apple", "Banana", "Mango"],
            "Dairy & Breakfast": ["Milk", "Curd", "Butter", "Cheese", "Bread", "Eggs"],
            "Atta, Rice & Dal": ["Atta", "Basmati Rice", "Toor Dal", "Moong Dal", "Besan"],
            "Snacks & Munchies": ["Biscuits", "Chips", "Chocolates", "Noodles", "Popcorn"],
            "Cold Drinks & Juices": ["Cola", "Orange Soda", "Mango Juice", "Energy Drink"],
            "Personal Care": ["Soap", "Shampoo", "Face Wash", "Toothpaste"],
            "Home & Cleaning": ["Detergent", "Dish Wash", "Floor Cleaner", "Toilet Cleaner"],
            "Electronics": ["Earphones", "Charger", "Mouse", "Keyboard", "Batteries"]
        }

        # ==========================================
        # 3. PRODUCT & INVENTORY SETUP (Bulk)
        # ==========================================
        print("🛒 Creating Products with Stock (Qty > 20)...")
        
        total_skus = 0
        variants = ["500g", "1kg", "Pack of 2", "Standard", "Large"]

        for cat_name, items in CATALOG_DATA.items():
            # Create Category
            category, _ = Category.objects.get_or_create(
                name=cat_name, 
                defaults={'slug': slugify(cat_name), 'is_active': True}
            )

            for item_name in items:
                # Har item ke 3-4 variants banate hain taaki catalog bhara dikhe
                for _ in range(3): 
                    variant = random.choice(variants)
                    full_name = f"{item_name} {variant}"
                    sku_code = f"{slugify(item_name).upper()[:4]}-{random.randint(10000, 99999)}"
                    price = random.randint(30, 1000)

                    sku, created = SKU.objects.get_or_create(
                        name=full_name,
                        defaults={
                            "sku_code": sku_code,
                            "category": category,
                            "brand": random.choice(brands),
                            "unit": "pack",
                            "sale_price": Decimal(price),
                            "cost_price": Decimal(price * 0.8),
                            "is_active": True,
                            "image_url": f"https://placehold.co/400x400/png?text={item_name.replace(' ', '+')}"
                        }
                    )

                    # --- INVENTORY LOGIC (Min 20 Qty) ---
                    # Har product ko random 2 bins mein rakhenge
                    stock_qty = random.randint(25, 200) # Always > 20
                    
                    # 1. Central Stock (InventoryStock)
                    inv_stock, _ = InventoryStock.objects.get_or_create(warehouse=wh, sku=sku)
                    inv_stock.available_qty = stock_qty
                    inv_stock.reserved_qty = 0
                    inv_stock.save()

                    # 2. Bin Stock (BinInventory) - Split qty randomly
                    if all_bins:
                        # Pick random bin
                        target_bin = random.choice(all_bins)
                        bin_inv, _ = BinInventory.objects.get_or_create(bin=target_bin, sku=sku)
                        bin_inv.qty = stock_qty
                        bin_inv.reserved_qty = 0
                        bin_inv.save()

                    total_skus += 1

        print(f"    ✅ Created {total_skus} Products with Stock.")

        # ==========================================
        # 4. FRONTEND SETUP (Banners & Sales)
        # ==========================================
        print("🎨 Setting up Banners & Flash Sales...")
        
        # Clear old
        Banner.objects.all().delete()
        FlashSale.objects.all().delete()

        banners = [
            ("Mega Savings", "HERO", "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"),
            ("Fresh Veggies", "HERO", "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"),
            ("Deal of the Day", "MID", "linear-gradient(135deg, #f6d365 0%, #fda085 100%)"),
        ]
        for idx, b in enumerate(banners):
            Banner.objects.create(
                title=b[0], position=b[1], bg_gradient=b[2], target_url="/search_results.html", 
                image_url="https://placehold.co/600x300", is_active=True, sort_order=idx
            )

        # Flash Sales (Pick 5 random items)
        all_skus = list(SKU.objects.all())
        if len(all_skus) > 5:
            for sku in random.sample(all_skus, 5):
                FlashSale.objects.create(
                    sku=sku,
                    discounted_price=sku.sale_price * Decimal("0.5"), # 50% Off
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(days=2),
                    total_quantity=50,
                    sold_quantity=random.randint(5, 20),
                    is_active=True
                )

    print("✅ SUCCESS: All Data Seeded Successfully!")

if __name__ == "__main__":
    try:
        run_seed()
    except Exception as e:
        print(f"❌ Error: {e}")