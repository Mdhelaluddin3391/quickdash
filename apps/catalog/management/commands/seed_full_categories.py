# apps/catalog/management/commands/seed_categories.py
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Category

class Command(BaseCommand):
    help = "Populate standard Zepto/Blinkit style categories"

    def handle(self, *args, **options):
        # Zepto/Blinkit Style Structure
        DATA = [
            ("Groceries & Essentials", [
                "Atta, Dal & Rice", "Edible Oils & Ghee", "Masalas & Spices", "Breakfast & Cereals"
            ]),
            ("Fresh Produce", [
                "Fresh Vegetables", "Fresh Fruits", "Exotic Fruits", "Cut Veggies"
            ]),
            ("Snacks & Beverages", [
                "Chips & Namkeen", "Soft Drinks", "Juices", "Chocolates", "Ice Creams"
            ]),
            ("Dairy, Bread & Eggs", [
                "Milk", "Bread & Butter", "Eggs", "Curd & Yogurt", "Paneer"
            ]),
            ("Personal Care", [
                "Skin Care", "Hair Care", "Oral Care", "Bath & Body"
            ]),
            ("Home Care", [
                "Cleaning Essentials", "Detergents", "Air Fresheners"
            ]),
            ("Instant Food", [
                "Noodles & Pasta", "Frozen Veg", "Ready-to-Eat"
            ]),
            ("Chicken, Meat & Fish", [
                "Fresh Chicken", "Mutton", "Seafood"
            ]),
            ("Pet Care", [
                "Dog Food", "Cat Food", "Accessories"
            ]),
            ("Baby Care", [
                "Diapers", "Baby Food", "Skincare"
            ])
        ]

        self.stdout.write("Seeding Categories...")

        for parent_name, subs in DATA:
            # 1. Parent Category (Major)
            parent_slug = slugify(parent_name)
            parent, created = Category.objects.get_or_create(
                name=parent_name,
                defaults={
                    'slug': parent_slug, 
                    'is_active': True,
                    # Demo icon placeholder (frontend JS will handle real icons or use generic)
                    'icon_url': 'https://cdn-icons-png.flaticon.com/512/3081/3081986.png' 
                }
            )
            
            if created:
                self.stdout.write(f"Created Parent: {parent_name}")
            
            # 2. Subcategories
            for sub_name in subs:
                sub_slug = slugify(f"{parent_name} {sub_name}") # Unique slug
                Category.objects.get_or_create(
                    name=sub_name,
                    parent=parent,
                    defaults={'slug': sub_slug, 'is_active': True}
                )

        self.stdout.write(self.style.SUCCESS("✅ Categories Seeded Successfully!"))