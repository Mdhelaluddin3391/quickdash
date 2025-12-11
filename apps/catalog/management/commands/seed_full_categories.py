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
    help = "Seeds Bulk Data: 15+ Main Categories, Deep nesting, and 50+ Products per category"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting MASSIVE Data Seeding...")

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
        
        # Ensure bin exists
        bin_obj, _ = Bin.objects.update_or_create(
            bin_code="B-001",
            defaults={'shelf': shelf, 'capacity': 5000.0}
        )

        # Expanded Brands List
        brand_names = [
            "Amul", "Nestle", "Britannia", "Tata", "Fortune", "Aashirvaad", 
            "Cadbury", "Lays", "Haldiram", "Himalaya", "Pampers", "Dettol", 
            "Surf Excel", "Vim", "Coca-Cola", "Pepsi", "Samsung", "Sony", 
            "Nike", "Adidas", "Loreal", "Nivea", "Dove", "Colgate", "Oral-B",
            "Classmate", "Reynolds", "Milton", "Prestige", "Pedigree", "Whiskas",
            "QuickDash Fresh"
        ]
        brands = []
        for b in brand_names:
            brand, _ = Brand.objects.get_or_create(name=b, defaults={'slug': slugify(b), 'is_active': True})
            brands.append(brand)

        # ---------------------------------------------------------
        # 2. MASTER DATA STRUCTURE (15+ Main Cats, Deep Nesting)
        # ---------------------------------------------------------
        
        CATALOG_DATA = {
            # 1. Fruits & Veg
            "Fruits & Vegetables": {
                "Fresh Vegetables": {
                    "Daily Veggies": ["Potato", "Onion", "Tomato", "Chilli", "Lemon", "Cucumber"],
                    "Root Vegetables": ["Carrot", "Beetroot", "Radish", "Sweet Potato", "Turnip"],
                    "Leafy Greens": ["Spinach", "Coriander", "Mint", "Methi", "Lettuce"],
                    "Gourd & Pumpkin": ["Bottle Gourd", "Bitter Gourd", "Pumpkin", "Ridge Gourd"]
                },
                "Fresh Fruits": {
                    "Seasonal Fruits": ["Mango", "Watermelon", "Muskmelon", "Grapes", "Orange"],
                    "Daily Fruits": ["Apple", "Banana", "Papaya", "Pomegranate", "Guava"],
                    "Exotic Fruits": ["Kiwi", "Dragon Fruit", "Avocado", "Blueberries", "Strawberries"]
                },
                "Organic & Hydroponic": ["Organic Tomato", "Organic Spinach", "Hydroponic Lettuce", "Organic Bell Peppers"]
            },
            
            # 2. Dairy & Breakfast
            "Dairy, Bread & Eggs": {
                "Milk & Curd": {
                    "Milk": ["Toned Milk", "Full Cream Milk", "Cow Milk", "Soy Milk", "Almond Milk"],
                    "Curd & Yogurt": ["Curd Pouch", "Greek Yogurt", "Flavored Yogurt", "Buttermilk", "Lassi"]
                },
                "Paneer, Butter & Cheese": {
                    "Butter": ["Salted Butter", "Unsalted Butter", "White Butter", "Garlic Butter"],
                    "Cheese": ["Cheese Slices", "Cheese Cubes", "Mozzarella Block", "Cheddar Cheese", "Cream Cheese"],
                    "Paneer & Cream": ["Fresh Paneer", "Malai Paneer", "Tofu", "Fresh Cream"]
                },
                "Bread & Bakery": ["White Bread", "Brown Bread", "Multigrain Bread", "Pav Bun", "Burger Bun", "Garlic Bread"]
            },
            
            # 3. Staples
            "Atta, Rice & Dal": {
                "Atta & Flours": ["Chakki Atta", "Maida", "Sooji", "Besan", "Rice Flour", "Multigrain Atta", "Ragi Flour"],
                "Rice & Rice Products": ["Basmati Rice", "Sona Masoori", "Poha", "Idli Rice", "Brown Rice", "Jasmine Rice"],
                "Dals & Pulses": ["Toor Dal", "Moong Dal", "Chana Dal", "Urad Dal", "Masoor Dal", "Rajma", "Kabuli Chana", "Green Gram"]
            },
            
            # 4. Spices & Oil
            "Masala, Oil & More": {
                "Edible Oils": ["Sunflower Oil", "Mustard Oil", "Ghee", "Olive Oil", "Groundnut Oil", "Coconut Oil", "Rice Bran Oil"],
                "Masalas & Spices": ["Turmeric Powder", "Chilli Powder", "Coriander Powder", "Garam Masala", "Jeera", "Mustard Seeds", "Black Pepper"],
                "Salt, Sugar & Jaggery": ["Iodized Salt", "Sugar", "Jaggery Cubes", "Rock Salt", "Brown Sugar", "Honey"]
            },
            
            # 5. Snacks
            "Snacks & Munchies": {
                "Biscuits & Cookies": ["Marie Gold", "Good Day", "Oreo", "Digestive", "Cream Biscuit", "Rusks", "Salted Crackers"],
                "Chips & Namkeen": ["Potato Chips", "Nachos", "Bhujia", "Mixture", "Peanuts", "Popcorn", "Banana Chips"],
                "Chocolates & Candies": ["Dairy Milk", "KitKat", "5 Star", "Gems", "Jelly Bears", "Lollipops", "Dark Chocolate"]
            },
            
            # 6. Beverages
            "Cold Drinks & Juices": {
                "Soft Drinks": ["Cola", "Orange Soda", "Lemon Drink", "Jeera Soda", "Ginger Ale", "Club Soda"],
                "Juices": ["Mango Juice", "Mixed Fruit Juice", "Apple Juice", "Orange Juice", "Guava Juice"],
                "Energy & Health": ["Energy Drink", "Ice Tea", "Electrolyte Drink", "Protein Shake"]
            },
            
            # 7. Hot Beverages
            "Tea, Coffee & Health": {
                "Tea": ["Premium Tea", "Green Tea", "Ginger Tea", "Masala Tea Bags", "Earl Grey", "Chamomile"],
                "Coffee": ["Instant Coffee", "Filter Coffee", "Coffee Beans", "Cappuccino Mix", "Espresso Powder"],
                "Health Drinks": ["Chocolate Health Drink", "Malt Drink", "Protein Powder", "Glucose Powder"]
            },
            
            # 8. Instant Food
            "Instant & Frozen Food": {
                "Noodles & Pasta": ["Instant Noodles", "Hakka Noodles", "Penne Pasta", "Macaroni", "Cup Noodles", "Spaghetti"],
                "Frozen Food": ["Frozen Peas", "French Fries", "Frozen Corn", "Veg Nuggets", "Chicken Nuggets", "Hash Browns"],
                "Ready to Eat": ["Ready Upma", "Ready Poha", "Instant Soup", "Dal Makhani Pack", "Rajma Rice Pack"]
            },
            
            # 9. Personal Care
            "Personal Care": {
                "Bath & Body": ["Soap Bar", "Body Wash", "Hand Wash", "Shower Gel", "Loofah"],
                "Hair Care": ["Shampoo", "Conditioner", "Hair Oil", "Hair Color", "Hair Serum"],
                "Skin & Face": ["Face Wash", "Moisturizer", "Sunscreen", "Face Cream", "Lip Balm", "Face Mask"],
                "Oral Care": ["Toothpaste", "Toothbrush", "Mouthwash", "Dental Floss"]
            },
            
            # 10. Home Care
            "Home & Cleaning": {
                "Detergents": ["Washing Powder", "Liquid Detergent", "Fabric Conditioner", "Stain Remover"],
                "Utensil Cleaners": ["Dish Wash Bar", "Dish Wash Liquid", "Steel Scrubber", "Sponge Wipe"],
                "Home Cleaners": ["Floor Cleaner", "Toilet Cleaner", "Bathroom Cleaner", "Glass Cleaner", "Furniture Polish"],
                "Disposables": ["Garbage Bags", "Paper Napkins", "Toilet Paper", "Kitchen Towels", "Aluminum Foil"]
            },
            
            # 11. Baby Care
            "Baby Care": {
                "Diapers & Wipes": ["Diapers S", "Diapers M", "Diapers L", "Diapers XL", "Baby Wipes", "Cloth Diapers"],
                "Baby Food": ["Apple Puree", "Cereal Mix", "Baby Biscuits", "Milk Formula"],
                "Baby Skin & Bath": ["Baby Oil", "Baby Soap", "Baby Shampoo", "Baby Powder", "Rash Cream"]
            },
            
            # 12. Beauty & Makeup (NEW)
            "Beauty & Makeup": {
                "Eyes & Lips": ["Kajal", "Eyeliner", "Mascara", "Lipstick", "Lip Gloss"],
                "Face": ["Foundation", "Compact Powder", "BB Cream", "Blush", "Makeup Remover"],
                "Nails": ["Nail Polish", "Nail Polish Remover", "Manicure Kit"]
            },
            
            # 13. Pet Care (NEW)
            "Pet Care": {
                "Dog Supplies": ["Dog Food Dry", "Dog Food Wet", "Dog Treats", "Dog Shampoo", "Leash"],
                "Cat Supplies": ["Cat Food Dry", "Cat Food Wet", "Cat Litter", "Cat Toys"],
                "Grooming": ["Pet Brush", "Tick Powder", "Pet Wipes"]
            },
            
            # 14. Stationery (NEW)
            "Stationery & Office": {
                "Pens & Pencils": ["Ball Pen Blue", "Ball Pen Black", "Gel Pen", "HB Pencils", "Highlighters"],
                "Paper & Notebooks": ["A4 Paper Rim", "Notebook Ruled", "Notebook Unruled", "Sticky Notes", "Diary"],
                "Art & Craft": ["Crayons", "Sketch Pens", "Water Colors", "Glue Stick", "Scissors"]
            },
            
            # 15. Electronics (NEW)
            "Electronics & Accessories": {
                "Mobile Accessories": ["Charging Cable Type-C", "Charging Cable Lightning", "Power Bank", "Earphones", "Mobile Stand"],
                "Computer Accessories": ["Wireless Mouse", "Keyboard", "Mouse Pad", "Pen Drive 32GB", "HDMI Cable"],
                "Batteries": ["AA Batteries", "AAA Batteries", "Coin Cells"]
            },

            # 16. Health & Pharma (NEW)
            "Health & Pharma": {
                "First Aid": ["Bandages", "Cotton Roll", "Antiseptic Liquid", "Pain Relief Spray"],
                "Supplements": ["Vitamin C", "Multivitamins", "Fish Oil", "Calcium Tablets"],
                "Sexual Wellness": ["Condoms", "Lubricants"]
            }
        }

        # ---------------------------------------------------------
        # 3. HELPER TO CREATE PRODUCTS
        # ---------------------------------------------------------
        def create_products_for_category(cat_obj, brand_obj, item_list, count_needed=50):
            # Variants to multiply items
            variants = ["500g", "1kg", "2kg", "Pack of 2", "Pack of 4", "Small", "Large", "Family Pack", "Combo"]
            
            created_count = 0
            
            # Loop until we satisfy the count (circularly iterating through items)
            while created_count < count_needed:
                for item_name in item_list:
                    if created_count >= count_needed: break
                    
                    variant = random.choice(variants)
                    full_name = f"{item_name} {variant}"
                    # Unique SKU Code
                    sku_code = f"{slugify(item_name).upper()[:5]}-{random.randint(10000, 99999)}-{created_count}"
                    
                    price = random.randint(20, 1500)
                    
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
                    
                    # Stock logic (50+ quantity as requested)
                    stock_qty = random.randint(50, 200)
                    
                    BinInventory.objects.update_or_create(bin=bin_obj, sku=sku, defaults={"qty": stock_qty, "reserved_qty": 0})
                    InventoryStock.objects.update_or_create(warehouse=wh, sku=sku, defaults={"available_qty": stock_qty, "reserved_qty": 0})
                    
                    created_count += 1

        # ---------------------------------------------------------
        # 4. MAIN LOOP
        # ---------------------------------------------------------
        
        for main_cat_name, sub_data in CATALOG_DATA.items():
            self.stdout.write(f"📂 Processing: {main_cat_name}")
            
            # Create Main Category
            main_cat, _ = Category.objects.get_or_create(
                name=main_cat_name,
                defaults={"slug": slugify(main_cat_name), "is_active": True, "sort_order": random.randint(1,20)}
            )

            if isinstance(sub_data, list):
                # Direct products under main category (unlikely in this structure but handling it)
                create_products_for_category(main_cat, random.choice(brands), sub_data, count_needed=50)

            elif isinstance(sub_data, dict):
                for sub_key, sub_val in sub_data.items():
                    # Level 2: Sub Category
                    sub_cat, _ = Category.objects.get_or_create(
                        name=sub_key,
                        parent=main_cat,
                        defaults={"slug": slugify(f"{main_cat_name} {sub_key}"), "is_active": True}
                    )

                    if isinstance(sub_val, list):
                        # Products directly under Sub Category
                        create_products_for_category(sub_cat, random.choice(brands), sub_val, count_needed=50)
                    
                    elif isinstance(sub_val, dict):
                        # Level 3: Sub-Sub Category
                        for sub_sub_key, items_list in sub_val.items():
                            sub_sub_cat, _ = Category.objects.get_or_create(
                                name=sub_sub_key,
                                parent=sub_cat,
                                defaults={"slug": slugify(f"{sub_key} {sub_sub_key}"), "is_active": True}
                            )
                            create_products_for_category(sub_sub_cat, random.choice(brands), items_list, count_needed=50)

        # ---------------------------------------------------------
        # 5. BANNERS & FLASH SALES
        # ---------------------------------------------------------
        self.stdout.write("🎨 Creating Banners & Sales...")
        Banner.objects.all().delete()
        FlashSale.objects.all().delete()

        # Hero Banners (Deal of the Day included in visuals)
        banners = [
            ("Mega Savings on Monthly Needs", "HERO", "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", "/category.html"),
            ("Fresh Fruits & Veggies - 40% OFF", "HERO", "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)", "/category.html"),
            ("Electronics Sale - Best Prices", "HERO", "linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)", "/category.html"),
            ("Beauty Bonanza", "HERO", "linear-gradient(135deg, #FF9A9E 0%, #FECFEF 100%)", "/category.html"),
            ("Deal of the Day - Snacks", "MID", "linear-gradient(135deg, #f6d365 0%, #fda085 100%)", "/category.html"),
            ("Pet Care Essentials", "MID", "linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%)", "/category.html"),
        ]
        
        for idx, b in enumerate(banners):
            Banner.objects.create(
                title=b[0], position=b[1], bg_gradient=b[2], target_url=b[3], 
                image_url="https://cdn-icons-png.flaticon.com/512/3081/3081559.png",
                is_active=True, sort_order=idx
            )

        # Flash Sales (Safe Unique Selection)
        all_skus = list(SKU.objects.all()[:500]) # Get a larger pool
        if all_skus:
            # Pick 8 unique items for Flash Sales
            pick_count = min(len(all_skus), 8)
            selected_skus = random.sample(all_skus, pick_count)
            
            for sku in selected_skus:
                FlashSale.objects.create(
                    sku=sku,
                    discounted_price=sku.sale_price * Decimal("0.6"), # 40% OFF
                    start_time=timezone.now(),
                    end_time=timezone.now() + timedelta(days=1),
                    total_quantity=100,
                    sold_quantity=random.randint(10, 50),
                    is_active=True
                )

        self.stdout.write(self.style.SUCCESS("✅ SUCCESS: Massive Data Seeded!"))