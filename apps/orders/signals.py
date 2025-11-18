# apps/orders/signals.py
from django.dispatch import Signal

# Jab future mein Orders app ko koi custom signal bhejna ho, toh yahan define karenge.
# Example: order_cancelled = Signal()
order_refund_requested = Signal()