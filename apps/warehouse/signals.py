# apps/warehouse/signals.py
from django.dispatch import Signal

# Signal fired when inventory levels physically change
inventory_change_required = Signal()

# Signal fired when a dispatch is ready for pickup
dispatch_ready_for_delivery = Signal()

# Signal fired when an item is cancelled during fulfillment
item_fulfillment_cancelled = Signal()

# Note: send_order_created has been moved to apps.orders.signals