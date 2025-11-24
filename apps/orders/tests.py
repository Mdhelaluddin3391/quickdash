# apps/orders/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.orders.models import Order, OrderCancellation, Cart, CartItem
from apps.orders.services import cancel_order
from apps.warehouse.models import Warehouse
from apps.catalog.models import SKU
from django.conf import settings


User = get_user_model()


class CancelOrderServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="+911234567890",
            password="testpass123",
        )
        self.warehouse = Warehouse.objects.create(
            name="Test WH",
            code="WH-1",
            address="Test address",
        )
        self.order = Order.objects.create(
            customer=self.user,
            warehouse=self.warehouse,
            status="pending",
            payment_status="paid",
            final_amount="100.00",
        )

    def test_cancel_order_creates_cancellation_and_timeline(self):
        ok, msg = cancel_order(self.order, cancelled_by="CUSTOMER", reason="User changed mind")

        self.assertTrue(ok, msg)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")

        # Cancellation record exists
        oc = OrderCancellation.objects.get(order=self.order)
        self.assertEqual(oc.cancelled_by, "CUSTOMER")
        self.assertIn("changed mind", oc.reason_text)

    def test_cannot_cancel_delivered_order(self):
        self.order.status = "delivered"
        self.order.save(update_fields=["status"])

        ok, msg = cancel_order(self.order, cancelled_by="CUSTOMER", reason="Too late")
        self.assertFalse(ok)
        self.assertIn("Cannot cancel", msg)


class CancelOrderAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone="+911111111111",
            password="testpass123",
        )
        self.other = User.objects.create_user(
            phone="+922222222222",
            password="testpass123",
        )
        self.warehouse = Warehouse.objects.create(
            name="Test WH",
            code="WH-2",
            address="Test address",
        )
        self.order = Order.objects.create(
            customer=self.user,
            warehouse=self.warehouse,
            status="pending",
            payment_status="pending",
            final_amount="50.00",
        )

    def _url(self, order):
        return reverse("order-cancel", kwargs={"pk": str(order.id)})

    def test_customer_can_cancel_within_window(self):
        self.client.force_authenticate(self.user)
        # Ensure created_at is recent (inside window)
        self.order.created_at = timezone.now()
        self.order.save(update_fields=["created_at"])

        resp = self.client.post(self._url(self.order), {"reason": "Need to cancel"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "cancelled")

    def test_cannot_cancel_after_window(self):
        self.client.force_authenticate(self.user)

        window_seconds = getattr(settings, "ORDER_CANCELLATION_WINDOW", 300)
        past = timezone.now() - timedelta(seconds=window_seconds + 10)
        self.order.created_at = past
        self.order.save(update_fields=["created_at"])

        resp = self.client.post(self._url(self.order), {"reason": "Too late"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_other_user_cannot_cancel_someone_elses_order(self):
        self.client.force_authenticate(self.other)
        resp = self.client.post(self._url(self.order), {"reason": "Hacker attempt"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class CartAndCheckoutSmokeTests(APITestCase):
    """
    Light-weight smoke tests:
    - Cart add/update
    - Checkout COD happy path (without real Razorpay)
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone="+933333333333",
            password="testpass123",
        )
        self.client.force_authenticate(self.user)

        self.warehouse = Warehouse.objects.create(
            name="Test WH",
            code="WH-3",
            address="Test address",
        )
        # Minimum SKU fields (adjust if your SKU model needs more)
        self.sku = SKU.objects.create(
            sku_code="SKU-1",
            name="Test Product",
            sale_price="25.00",
            mrp="30.00",
            is_active=True,
        )

    def test_add_to_cart_and_checkout_cod(self):
        # 1. Add item to cart
        add_url = reverse("cart-add")
        resp = self.client.post(add_url, {"sku_id": str(self.sku.id), "quantity": 2}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # 2. Checkout COD
        create_url = reverse("create-order")
        payload = {
            "warehouse_id": str(self.warehouse.id),
            "items": [
                {"sku_id": str(self.sku.id), "quantity": 2}
            ],
            "delivery_address_json": {"line1": "Test street", "city": "City"},
            "payment_method": "COD",
        }
        resp = self.client.post(create_url, payload, format="json")
        self.assertIn(resp.status_code, [status.HTTP_201_CREATED, status.HTTP_200_OK])
        self.assertIn("order_id", resp.data)
