from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Transaction, TransactionStatus, PaymentMethod
from apps.orders.models.order import Order, OrderStatus
from django.contrib.auth import get_user_model
from apps.warehouse.models import Warehouse
from apps.payments.services import PaymentService
import uuid
import hmac
import hashlib

User = get_user_model()

class PaymentWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('payment-webhook') # Ensure this name matches urls.py
        
        # Setup prerequisites
        self.user = User.objects.create(phone_number="+919999999999")
        self.warehouse = Warehouse.objects.create(
            name="Test WH", latitude=0, longitude=0, address="Test"
        )
        self.order = Order.objects.create(
            user=self.user,
            warehouse=self.warehouse,
            total_amount=100.00,
            status=OrderStatus.PENDING_PAYMENT,
            delivery_address_snapshot={}
        )
        self.transaction = Transaction.objects.create(
            order=self.order,
            user=self.user,
            amount=100.00,
            payment_method=PaymentMethod.RAZORPAY,
            provider_order_id="order_123",
            status=TransactionStatus.INITIATED
        )
        self.secret = "test_secret"
        
        # Inject secret into settings for test context
        from django.conf import settings
        self.original_secret = getattr(settings, 'PAYMENT_WEBHOOK_SECRET', None)
        settings.PAYMENT_WEBHOOK_SECRET = self.secret

    def tearDown(self):
        from django.conf import settings
        if self.original_secret:
            settings.PAYMENT_WEBHOOK_SECRET = self.original_secret

    def _get_signature(self, payload):
        return hmac.new(
            bytes(self.secret, 'utf-8'),
            bytes(payload, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

    def test_webhook_success(self):
        """Verify valid signature leads to processed payment"""
        payload_data = {
            "payload": {
                "payment": {"entity": {"id": "pay_123"}},
                "order": {"entity": {"id": "order_123"}}
            }
        }
        import json
        payload_str = json.dumps(payload_data)
        signature = self._get_signature(payload_str)
        
        response = self.client.post(
            self.url, 
            data=payload_data, 
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, TransactionStatus.SUCCESS)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PAID)

    def test_webhook_invalid_signature(self):
        """Verify invalid signature returns 403"""
        payload_data = {"test": "data"}
        import json
        payload_str = json.dumps(payload_data)
        
        response = self.client.post(
            self.url, 
            data=payload_data, 
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE="fake_signature"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_webhook_idempotency(self):
        """Verify duplicate webhooks do not double process"""
        # First call success
        self.test_webhook_success()
        
        # Second call
        payload_data = {
            "payload": {
                "payment": {"entity": {"id": "pay_123"}},
                "order": {"entity": {"id": "order_123"}}
            }
        }
        import json
        payload_str = json.dumps(payload_data)
        signature = self._get_signature(payload_str)
        
        response = self.client.post(
            self.url, 
            data=payload_data, 
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should remain SUCCESS, no errors