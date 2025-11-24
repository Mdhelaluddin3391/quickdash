from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.orders.models import Cart, CartItem, Order
from apps.catalog.models import SKU

User = get_user_model()

class OrderFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone='9999999999')
        self.sku = SKU.objects.create(sku_code='SKU1', name='Test SKU', sale_price=100)
        self.cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(cart=self.cart, sku=self.sku, quantity=2)

    def test_create_order_from_cart(self):
        from apps.orders.services import create_order_from_cart
        order, payment, err = create_order_from_cart(self.user, None, {'address': 'x'})
        self.assertIsNone(err)
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
