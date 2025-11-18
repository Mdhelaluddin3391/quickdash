from django.dispatch import Signal

# Jab Dispatch ready ho jaye (Packing complete hone par)
dispatch_ready_for_delivery = Signal()

# Jab order create ho (Orders app se WMS ko batane ke liye)
send_order_created = Signal()