import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("confirmed", "Confirmed"),
    ("picking", "Picking"),
    ("packed", "Packed"),
    ("ready", "Ready for Dispatch"),
    ("dispatched", "Dispatched"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
]

PAYMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("authorized", "Authorized"),
    ("paid", "Paid"),
    ("refunded", "Refunded"),
]

class Coupon(models.Model):
    """Discount Coupon Model"""
    code = models.CharField(max_length=50, unique=True)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_percentage = models.BooleanField(default=False)
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    times_used = models.PositiveIntegerField(default=0)
"""Top-level models import shim.

This file re-exports models from the `models` package so existing imports
(`from apps.orders import models` or `from .models import Order`) continue to work.
"""

from .models.order import *
from .models.item import *
from .models.timeline import *
from .models.cancellation import *
from .models.cart import *
