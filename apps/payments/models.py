# apps/payments/models.py
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings


class Payment(models.Model):
    """
    Final recorded payment against an Order.

    - Each successful online payment = 1 Payment row (RAZORPAY).
    - COD orders may also have a Payment row (method=COD).
    - Refunds always link to a Payment.
    """

    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"
        RAZORPAY = "RAZORPAY", "Razorpay"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESSFUL = "SUCCESSFUL", "Successful"        # captured / completed
        FAILED = "FAILED", "Failed"
        REFUND_INITIATED = "REFUND_INITIATED", "Refund Initiated"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )

    # Gateway identifiers
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Payment Gateway Payment ID (e.g. pay_Hj8...)",
    )
    gateway_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Razorpay Order ID (e.g. order_Hj8...)",
    )

    gateway_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_successful(self, gateway_payload=None):
        self.status = self.PaymentStatus.SUCCESSFUL
        if gateway_payload is not None:
            self.gateway_response = gateway_payload
        self.save(update_fields=["status", "gateway_response", "updated_at"])

    def mark_failed(self, error_message=None):
        self.status = self.PaymentStatus.FAILED
        if error_message:
            self.gateway_response = {
                **self.gateway_response,
                "error": str(error_message),
            }
        self.save(update_fields=["status", "gateway_response", "updated_at"])

    def __str__(self):
        return f"Payment({self.id}) Order={self.order_id} {self.status}"


class PaymentIntent(models.Model):
    """
    Represents a "payable intent" for an order.

    - One order may have multiple PaymentIntents (retries).
    - Each intent corresponds to a Razorpay Order ID.
    """

    class IntentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="intents",
    )

    gateway_order_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        db_index=True,
    )
    gateway_payment_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")

    status = models.CharField(
        max_length=30,
        choices=IntentStatus.choices,
        default=IntentStatus.PENDING,
    )

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Intent {self.id} for Order {self.order_id} ({self.status})"


class Refund(models.Model):
    """
    Refund record against a Payment (usually Razorpay).

    - Created when Orders emits order_refund_requested.
    - Celery task calls gateway and updates status.
    """

    class RefundStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="refunds",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="refunds",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=RefundStatus.choices,
        default=RefundStatus.PENDING,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)

    gateway_refund_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Razorpay refund ID",
    )
    gateway_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund {self.id} for Payment {self.payment_id} ({self.status})"

    @property
    def is_success(self) -> bool:
        return self.status == self.RefundStatus.SUCCESS
