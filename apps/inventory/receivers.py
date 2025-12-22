from django.dispatch import receiver
from django.db.models.signals import post_save
# from .signals import inventory_change_required  <-- REMOVED
from .models import InventoryStock

# CRITICAL FIX: Removed the implicit signal receiver for inventory sync.
# This logic has been moved to apps.warehouse.services.WarehouseService.update_bin_inventory
# to ensure deterministic transaction execution.

# Retaining only non-critical receivers if any exist in future.
# Currently empty to prevent circular import and implicit updates.