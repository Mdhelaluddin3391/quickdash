# apps/payments/tests.py
from django.test import TestCase
from apps.orders.models import Order
from apps.accounts.models import User
from .models import Payment
from decimal import Decimal

class PaymentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(phone="+919999999999")
        self.order = Order.objects.create(
            customer=self.user,
            final_amount=Decimal("100.00")
        )

    def test_create_payment(self):
        payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("100.00"),
            payment_method=Payment.PaymentMethod.COD
        )
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.amount, Decimal("100.00"))