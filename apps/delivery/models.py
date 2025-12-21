# apps/delivery/models.py
import uuid
import logging
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from apps.orders.models import Order
from apps.accounts.models import RiderProfile
from apps.utils.models import TimestampedModel

logger = logging.getLogger(__name__)


class DeliveryTask(TimestampedModel):
    """
    Single order ki delivery lifecycle track karta hai.

    Status Flow:
    - PENDING_ASSIGNMENT  → rider search in progress
    - ACCEPTED            → rider ne job accept kiya
    - AT_STORE            → rider store/warehouse par pohonch gaya
    - PICKED_UP           → order pickup ho gaya (COD cash with rider)
    - DELIVERED           → customer ko deliver ho gaya
    - CANCELLED / FAILED  → delivery nahi ho payi
    """

    class DeliveryStatus(models.TextChoices):
        PENDING_ASSIGNMENT = "PENDING_ASSIGNMENT", "Pending Assignment"
        ACCEPTED = "ACCEPTED", "Accepted by Rider"
        AT_STORE = "AT_STORE", "Rider at Store"
        PICKED_UP = "PICKED_UP", "Picked Up"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Primary link
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='delivery_task')

    # Assigned rider (optional before assignment)
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )

    # WMS dispatch record reference
    dispatch_record_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Reference to WMS DispatchRecord (if any).",
    )

    status = models.CharField(
        max_length=32,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING_ASSIGNMENT,
        db_index=True,
    )

    # OTPs
    pickup_otp = models.CharField(max_length=10, blank=True)
    delivery_otp = models.CharField(max_length=10, blank=True)

    # Timestamps
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Ratings (customer -> rider)
    rider_rating = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    rider_rating_comment = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        """
        - Order + Rider state sync
        - Earning create on first DELIVERED
        - delivery_completed signal fire
        """
        from .signals import delivery_completed  # local import to avoid cycles

        is_new = self._state.adding
        old_status = None
        if not is_new:
            try:
                old_status = (
                    DeliveryTask.objects.only("status")
                    .get(pk=self.pk)
                    .status
                )
            except DeliveryTask.DoesNotExist:
                old_status = None

        # --- Order state sync ---
        if self.status == self.DeliveryStatus.PICKED_UP:
            # WMS se dispatch ke baad order.status already "dispatched" ho chuka hoga,
            # yahan ensure kar rahe hain.
            if self.order.status != "dispatched":
                self.order.status = "dispatched"
                self.order.save(update_fields=["status"])

        elif self.status == self.DeliveryStatus.DELIVERED:
            # In case Razorpay / COD finalization
            self.order.status = "delivered"
            if self.order.payment_status != "paid":
                self.order.payment_status = "paid"
            self.order.delivered_at = self.delivered_at
            self.order.save(
                update_fields=["status", "payment_status", "delivered_at"]
            )

        # --- Rider state sync ---
        if self.rider:
            if self.status in (
                self.DeliveryStatus.ACCEPTED,
                self.DeliveryStatus.AT_STORE,
                self.DeliveryStatus.PICKED_UP,
            ):
                self.rider.on_delivery = True
            elif self.status in (
                self.DeliveryStatus.DELIVERED,
                self.DeliveryStatus.CANCELLED,
                self.DeliveryStatus.FAILED,
            ):
                self.rider.on_delivery = False
            self.rider.save(update_fields=["on_delivery"])

        super().save(*args, **kwargs)

        # --- Post-save: create earning + emit signal on first DELIVERED ---
        if (
            not is_new
            and old_status != self.DeliveryStatus.DELIVERED
            and self.status == self.DeliveryStatus.DELIVERED
        ):
            self.create_rider_earning()
            try:
                rider_code = (
                    self.rider.rider_code if self.rider else "UNKNOWN"
                )
                delivery_completed.send(
                    sender=DeliveryTask,
                    order=self.order,
                    rider_code=rider_code,
                )
            except Exception:
                logger.exception(
                    "Failed to emit delivery_completed signal for task %s",
                    self.pk,
                )

    def create_rider_earning(self):
        if not self.rider:
            return
        try:
            base_fee = getattr(
                settings, "RIDER_BASE_FEE", Decimal("15.00")
            )
            tip = (
                self.order.rider_tip
                if hasattr(self.order, "rider_tip") and self.order.rider_tip
                else Decimal("0.00")
            )
            RiderEarning.objects.create(
                rider=self.rider,
                delivery_task=self,
                order_id_str=str(self.order.id),
                base_fee=base_fee,
                tip=tip,
                total_earning=base_fee + tip,
            )
            logger.info(
                "Rider earning created for rider=%s, task=%s",
                self.rider.id,
                self.id,
            )
        except Exception:
            logger.exception(
                "Failed to create earning for delivery task %s", self.id
            )

    def __str__(self):
        return f"DeliveryTask({self.order_id}) - {self.status}"


class RiderEarning(TimestampedModel):
    """
    Per-delivery earning line item (base fee + tip).
    Settlement / payouts RiderPayout se hoti hai.
    """

    class EarningStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PAID = "PAID", "Paid"

    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name="earnings",
    )
    delivery_task = models.OneToOneField(
        DeliveryTask,
        on_delete=models.SET_NULL,
        null=True,
        related_name="earning",
    )
    order_id_str = models.CharField(max_length=50)

    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    tip = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    total_earning = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=10,
        choices=EarningStatus.choices,
        default=EarningStatus.UNPAID,
    )

    def __str__(self):
        return f"{self.rider_id} / {self.order_id_str} -> {self.total_earning}"


class RiderPayout(TimestampedModel):
    """
    Backoffice ne jab rider ko settlement kiya (UPI / bank transfer).
    """

    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.PROTECT,
        related_name="payouts",
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_ref = models.CharField(max_length=100, blank=True)
    earnings_covered = models.ManyToManyField(
        RiderEarning,
        related_name="payouts",
    )

    def __str__(self):
        return f"{self.rider_id} / {self.amount_paid}"


class RiderCashDeposit(TimestampedModel):
    """
    Rider COD cash company ko jab deposit karta hai.
    """

    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.PROTECT,
        related_name="cash_deposits",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        default="PENDING",
        help_text="PENDING/VERIFIED/REJECTED",
    )
    proof_image = models.ImageField(
        upload_to="deposits/", null=True, blank=True
    )

    def __str__(self):
        return f"{self.rider_id} / {self.amount} ({self.status})"


class RiderApplication(TimestampedModel):
    """
    Rider onboarding application (optional future flow).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rider_application",
    )
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    status = models.CharField(
        max_length=20,
        default="PENDING",
        help_text="PENDING/APPROVED/REJECTED",
    )

    def __str__(self):
        return f"RiderApplication({self.phone}, {self.status})"
