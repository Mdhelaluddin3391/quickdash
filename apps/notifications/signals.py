# apps/notifications/signals.py
from django.dispatch import Signal

# Optional custom signals if you want to trigger notifications manually
order_created_notification = Signal()
order_dispatched_notification = Signal()
order_delivered_notification = Signal()
