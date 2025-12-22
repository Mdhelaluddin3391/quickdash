from django.dispatch import Signal

# Sent when Order is Paid & Confirmed
send_order_created = Signal()