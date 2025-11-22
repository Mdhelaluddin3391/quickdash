"""
Top-level models import shim for the Orders app.

Is file ka kaam sirf itna hai ki:
    from apps.orders.models import Order
ya
    from apps.orders import models

jaise imports properly kaam karein, jabki actual models
alag-alag files mein modular form mein pade hain.
"""

from .order import *          # Order, Coupon, ORDER_STATUS_CHOICES, PAYMENT_STATUS_CHOICES
from .item import *           # OrderItem
from .timeline import *       # OrderTimeline
from .cancellation import *   # OrderCancellation
from .cart import *           # Cart, CartItem
