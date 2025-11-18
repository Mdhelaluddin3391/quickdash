# apps/warehouse/signals.py
from django.dispatch import Signal

# Jab Dispatch ready ho jaye
dispatch_ready_for_delivery = Signal()

# Jab order create ho
send_order_created = Signal()

# Inventory stock changes
inventory_change_required = Signal()

# Jab koi item warehouse se cancel ho jaye (Naya Signal)
item_fulfillment_cancelled = Signal()