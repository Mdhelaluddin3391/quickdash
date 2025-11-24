# apps/delivery/tests.py
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order
from apps.warehouse.models import Warehouse
from apps.accounts.models import RiderProfile
from .models import DeliveryTask, RiderEarning

User = get_user_model()


class DeliveryFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="9100000000", password="test", is_rider=True
        )
        self.rider = RiderProfile.objects.create(
            user=self.user,
            rider_code="R-001",
            on_duty=True,
        )
        self.wh = Warehouse.objects.create(
            name="WH1",
            code="WH-1",
            address="Test",
            lat=12.97,
            lng=77.59,
            is_active=True,
        )
        self.order = Order.objects.create(
            customer=self.user,
            warehouse=self.wh,
            status="ready",
            final_amount=Decimal("100.00"),
        )

    def test_delivery_lifecycle_creates_earning(self):
        task = DeliveryTask.objects.create(
            order=self.order,
            rider=self.rider,
            status=DeliveryTask.DeliveryStatus.PICKED_UP,
            pickup_otp="1111",
            delivery_otp="2222",
        )

        # move to delivered
        task.status = DeliveryTask.DeliveryStatus.DELIVERED
        task.delivered_at = timezone.now()
        task.save()

        earning = RiderEarning.objects.filter(delivery_task=task).first()
        self.assertIsNotNone(earning)
        self.assertEqual(earning.rider, self.rider)
