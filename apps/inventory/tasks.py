import logging
from celery import shared_task
from django.db import transaction
from django.db.models import Sum, F
from apps.warehouse.models import BinInventory
from .models import InventoryStock, StockMovementLog

logger = logging.getLogger("django")

@shared_task(time_limit=1200) # 20 mins max
def run_reconciliation():
    """
    Nightly Job: Ensures Logical Stock (InventoryStock) matches Physical Stock (BinInventory).
    """
    logger.info("Starting Inventory Reconciliation...")
    
    # 1. Fetch all Logical Stocks
    stocks = InventoryStock.objects.all().select_related('warehouse', 'product')
    
    mismatch_count = 0
    
    for stock in stocks:
        with transaction.atomic():
            # 2. Sum Physical Bins for this SKU + Warehouse
            physical_sum = BinInventory.objects.filter(
                bin__zone__warehouse=stock.warehouse,
                sku=stock.product
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # 3. Compare
            if stock.quantity != physical_sum:
                diff = physical_sum - stock.quantity
                
                logger.warning(
                    f"Mismatch found! {stock.warehouse.code} - {stock.product.sku_code}: "
                    f"Logical={stock.quantity}, Physical={physical_sum}. Adjusting by {diff}."
                )
                
                # 4. Auto-Correction (Trust Physical)
                stock.quantity = physical_sum
                stock.save(update_fields=['quantity'])
                
                # 5. Log the system correction
                StockMovementLog.objects.create(
                    inventory=stock,
                    quantity_change=diff,
                    movement_type=StockMovementLog.MovementType.RECONCILIATION,
                    reference="NIGHTLY_AUTO_RECON",
                    balance_after=physical_sum
                )
                mismatch_count += 1

    logger.info(f"Reconciliation Complete. Fixed {mismatch_count} mismatches.")
    return f"Fixed {mismatch_count} items"