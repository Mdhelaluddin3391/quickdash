import uuid
import logging
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.gis.db import models as gis_models
from django.core.validators import MinValueValidator, MaxValueValidator

# Apps Imports (Aapke structure ke hisaab se)
from apps.orders.models import Order
from apps.accounts.models import RiderProfile
from apps.utils.models import TimestampedModel

logger = logging.getLogger(__name__)



# ==========================================
# 2. DELIVERY TASK (Main Logic)
# ==========================================
class DeliveryTask(TimestampedModel):
    """
    Order delivery process track karta hai.
    'Best' project mein ise 'Delivery' kaha gaya tha.
    """
    class DeliveryStatus(models.TextChoices):
        PENDING_ASSIGNMENT = 'PENDING_ASSIGNMENT', 'Pending Assignment'
        ACCEPTED = 'ACCEPTED', 'Accepted by Rider'
        AT_STORE = 'AT_STORE', 'Rider at Store'
        PICKED_UP = 'PICKED_UP', 'Picked Up'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Link to Order (Primary)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_task')
    
    # Link to Rider
    rider = models.ForeignKey(RiderProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    
    # WMS Link (Optional ab)
    dispatch_record_id = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(max_length=30, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING_ASSIGNMENT, db_index=True)
    
    # OTPs
    pickup_otp = models.CharField(max_length=10, blank=True)
    delivery_otp = models.CharField(max_length=10, blank=True)

    # Timestamps
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Ratings
    rider_rating = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    rider_rating_comment = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        # 1. Status Change Detection
        is_new = self._state.adding
        old_status = None
        if not is_new:
            old_status = DeliveryTask.objects.get(pk=self.pk).status

        # 2. Auto Update Order Status
        if self.status == self.DeliveryStatus.PICKED_UP:
            self.order.status = 'dispatched' # Ensure match Order model choices
            self.order.save()
        elif self.status == self.DeliveryStatus.DELIVERED:
            self.order.status = 'delivered'
            self.order.payment_status = 'paid' # COD confirm
            self.order.save()

        # 3. Update Rider State
        if self.rider:
            if self.status in [self.DeliveryStatus.ACCEPTED, self.DeliveryStatus.PICKED_UP]:
                self.rider.on_delivery = True
            elif self.status in [self.DeliveryStatus.DELIVERED, self.DeliveryStatus.CANCELLED, self.DeliveryStatus.FAILED]:
                self.rider.on_delivery = False
            self.rider.save()

        super().save(*args, **kwargs)

        # 4. Post-Save Logic: Create Earning Record on Delivery
        if not is_new and old_status != self.DeliveryStatus.DELIVERED and self.status == self.DeliveryStatus.DELIVERED:
            self.create_rider_earning()

    def create_rider_earning(self):
        if not self.rider: return
        try:
            # Simple calculation (Settings se value le sakte hain)
            base_fee = settings.RIDER_BASE_FEE 
            tip = self.order.rider_tip if hasattr(self.order, 'rider_tip') else Decimal('0.00')
            
            RiderEarning.objects.create(
                rider=self.rider,
                delivery_task=self,
                order_id_str=str(self.order.id),
                base_fee=base_fee,
                tip=tip,
                total_earning=base_fee + tip
            )
            logger.info(f"Earning created for Rider {self.rider.user.username}")
        except Exception as e:
            logger.error(f"Failed to create earning: {e}")

# ==========================================
# 3. RIDER FINANCIALS (Earnings & Payouts)
# ==========================================
class RiderEarning(TimestampedModel):
    class EarningStatus(models.TextChoices):
        UNPAID = 'UNPAID', 'Unpaid'
        PAID = 'PAID', 'Paid'

    rider = models.ForeignKey(RiderProfile, on_delete=models.CASCADE, related_name='earnings')
    delivery_task = models.OneToOneField(DeliveryTask, on_delete=models.SET_NULL, null=True)
    order_id_str = models.CharField(max_length=50)
    
    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    tip = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_earning = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=10, choices=EarningStatus.choices, default=EarningStatus.UNPAID)

class RiderPayout(TimestampedModel):
    rider = models.ForeignKey(RiderProfile, on_delete=models.PROTECT, related_name='payouts')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_ref = models.CharField(max_length=100, blank=True)
    earnings_covered = models.ManyToManyField(RiderEarning, related_name='payouts')

class RiderCashDeposit(TimestampedModel):
    """Rider depositing COD cash back to company"""
    rider = models.ForeignKey(RiderProfile, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='PENDING')
    proof_image = models.ImageField(upload_to='deposits/', null=True, blank=True)

# ==========================================
# 4. APPLICATION & DOCS
# ==========================================
class RiderApplication(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=20, default='PENDING')
