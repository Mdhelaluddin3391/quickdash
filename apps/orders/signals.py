# apps/orders/signals.py
from django.dispatch import Signal

# Orders app signals — keep only signals that are owned by Orders app.
# Use the canonical `payment_succeeded` from `apps.payments.signals` so all apps
# listen to a single source of truth for payment success events.
order_refund_requested = Signal()