# apps/inventory/services.py
from django.db import transaction
from django.db.models import F
from apps.inventory.models import InventoryStock

def check_and_lock_inventory(warehouse_id, sku_id, quantity):
    """
    Single Item Lock
    """
    stock = InventoryStock.objects.select_for_update().get(
        warehouse_id=warehouse_id, 
        sku_id=sku_id
    )
    if stock.available_qty < quantity:
        raise ValueError(f"Insufficient stock for SKU {sku_id}")
    return stock

def batch_check_and_lock_inventory(warehouse_id, items_list):
    """
    items_list: [{'sku': sku_obj, 'quantity': int}, ...]
    Locks InventoryStock rows in deterministic order to prevent deadlocks.
    """
    # Sort by SKU ID to prevent deadlocks
    items_list = sorted(items_list, key=lambda x: x['sku'].id)
    
    sku_ids = [i['sku'].id for i in items_list]
    
    # Fetch all stocks in one query with lock
    stocks = InventoryStock.objects.select_for_update().filter(
        warehouse_id=warehouse_id,
        sku_id__in=sku_ids
    )
    stock_map = {s.sku_id: s for s in stocks}

    for item in items_list:
        sku_id = item['sku'].id
        qty = item['quantity']
        
        stock = stock_map.get(sku_id)
        if not stock:
            raise ValueError(f"Stock record not found for SKU {item['sku'].sku_code}")
        
        if stock.available_qty < qty:
            raise ValueError(f"Insufficient stock for {item['sku'].name} (Requested: {qty}, Available: {stock.available_qty})")
        


# We do NOT deduct here. The Order Service deduces Logical Stock, 
        # or Warehouse Service deduces Physical Stock.
        # This function primarily validates and holds the lock. 