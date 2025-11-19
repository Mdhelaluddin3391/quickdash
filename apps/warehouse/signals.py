from django.dispatch import Signal

# Signal fired when inventory levels physically change (for analytics or notifications)
# args: sender, sku_id, warehouse_id, delta_available, delta_reserved, reference, change_type
inventory_change_required = Signal()

# Signal fired when a dispatch is ready for pickup
# args: sender, order_id, warehouse_id
dispatch_ready_for_delivery = Signal()

# Signal fired when an item is cancelled during fulfillment
# args: sender, order_id, sku_id, qty, reason
item_fulfillment_cancelled = Signal()