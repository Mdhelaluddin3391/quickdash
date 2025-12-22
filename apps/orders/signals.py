from django.dispatch import Signal

# Defined here, fired by Service or Receivers
order_created = Signal() 
order_status_changed = Signal()