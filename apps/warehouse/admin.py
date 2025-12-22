from django.contrib import admin, messages
from .services import PutawayService

@admin.action(description="Process GRN Stock (Smart Putaway)")
def process_grn_stock(modeladmin, request, queryset):
    for grn_item in queryset:
        if grn_item.status == 'PROCESSED':
            continue
            
        try:
            plan = PutawayService.execute_grn(
                sku=grn_item.sku,
                total_quantity=grn_item.quantity,
                warehouse=grn_item.warehouse
            )
            grn_item.status = 'PROCESSED'
            grn_item.save()
            
            # Log the distribution for the admin
            msg = ", ".join([f"{qty} -> {bin.code}" for bin, qty in plan])
            messages.success(request, f"Stored {grn_item.sku}: {msg}")
            
        except Exception as e:
            messages.error(request, f"Failed {grn_item.sku}: {str(e)}")

class GRNAdmin(admin.ModelAdmin):
    actions = [process_grn_stock]