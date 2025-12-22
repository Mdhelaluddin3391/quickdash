from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from apps.catalog.models import Product, Category
from apps.warehouse.models import Warehouse
from apps.inventory.models import WarehouseInventory
from apps.orders.services import OrderService
from apps.customers.models import CustomerProfile, Address
import concurrent.futures

User = get_user_model()

class ConcurrencyTests(TransactionTestCase):
    # Use TransactionTestCase to allow real DB transactions for concurrency testing
    
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="WH1", latitude=0, longitude=0)
        self.category = Category.objects.create(name="Cat1")
        self.product = Product.objects.create(name="Prod1", base_price=100, category=self.category)
        
        # Only 1 item in stock
        WarehouseInventory.objects.create(
            warehouse=self.warehouse, product=self.product, quantity=1, reserved_quantity=0
        )
        
        # Setup 2 users
        self.user1 = User.objects.create(phone_number="+911111111111")
        CustomerProfile.objects.create(user=self.user1)
        self.addr1 = Address.objects.create(
            customer=self.user1.customer_profile, 
            latitude=0, longitude=0, 
            address_line_1="Addr1", city="City", pincode="123"
        )
        # Create cart for user 1 (Mocking service dependency usually, but here strict DB test)
        from apps.orders.models.cart import Cart, CartItem
        c1 = Cart.objects.create(user=self.user1)
        CartItem.objects.create(cart=c1, product=self.product, quantity=1)

        self.user2 = User.objects.create(phone_number="+912222222222")
        CustomerProfile.objects.create(user=self.user2)
        self.addr2 = Address.objects.create(
            customer=self.user2.customer_profile,
            latitude=0, longitude=0, 
            address_line_1="Addr2", city="City", pincode="123"
        )
        c2 = Cart.objects.create(user=self.user2)
        CartItem.objects.create(cart=c2, product=self.product, quantity=1)

    def test_concurrent_ordering(self):
        """Verify that two users cannot buy the last item simultaneously"""
        def place_order(user_id, addr_id):
            user = User.objects.get(id=user_id)
            try:
                OrderService.create_order_from_cart(user, addr_id, 0, 0)
                return "SUCCESS"
            except Exception as e:
                return "FAILED"

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(place_order, self.user1.id, self.addr1.id),
                executor.submit(place_order, self.user2.id, self.addr2.id)
            ]
            results = [f.result() for f in futures]
            
        # One must succeed, one must fail
        self.assertEqual(results.count("SUCCESS"), 1)
        self.assertEqual(results.count("FAILED"), 1)