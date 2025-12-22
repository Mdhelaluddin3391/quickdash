# apps/payments/models.py

import uuid
from django.db import models
from django.conf import settings
from apps.orders.models import Order


class PaymentIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment_intent")
    gateway = models.CharField(max_length=50)  # e.g. razorpay
    amount = models.PositiveIntegerField()  # paise
    currency = models.CharField(max_length=10, default="INR")
    gateway_order_id = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Payment(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payments")
    intent = models.ForeignKey(PaymentIntent, on_delete=models.PROTECT, related_name="payments")
    gateway_payment_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    raw_payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)


class Refund(models.Model):
    class Status(models.TextChoices):
        INITIATED = "INITIATED"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices)
    gateway_refund_id = models.CharField(max_length=100, null=True, blank=True)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)


class WebhookLog(models.Model):
    """
    Idempotency guard: each webhook event processed once.
    """
    event_id = models.CharField(max_length=100, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
