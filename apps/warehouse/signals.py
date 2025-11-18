from django.dispatch import Signal

# --- Signal (payments/orders -> wms) ---
send_order_created = Signal()

# --- Signal (wms -> delivery) ---
dispatch_ready_for_delivery = Signal()