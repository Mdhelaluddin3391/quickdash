# apps/payments/signals.py
from django.dispatch import Signal

# Yeh signal tab bhejenge jab payment successful hoga
payment_succeeded = Signal()