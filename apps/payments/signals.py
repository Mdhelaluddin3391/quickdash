# apps/payments/signals.py
from django.dispatch import Signal

# Fired when a payment is fully successful (online payment).
# Orders app should listen to this to mark order as 'paid'.
payment_succeeded = Signal()
