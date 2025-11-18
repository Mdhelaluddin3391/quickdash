from django.dispatch import Signal

# --- Signal (delivery -> wms) ---
rider_assigned_to_dispatch = Signal()

# --- Signal (delivery -> orders) ---
delivery_completed = Signal()