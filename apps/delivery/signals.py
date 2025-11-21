# apps/delivery/signals.py
from django.dispatch import Signal

# delivery -> WMS / Orders
rider_assigned_to_dispatch = Signal()
delivery_completed = Signal()
