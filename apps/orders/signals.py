# apps/orders/signals.py
from django.dispatch import Signal

# Orders app signals
order_refund_requested = Signal()

# Signal fired when a new order is confirmed and needs warehouse allocation
# args: order_id, warehouse_id, items
send_order_created = Signal()