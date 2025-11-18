from django.contrib import admin
from .models import Warehouse, Zone, Bin, BinInventory, PickingTask, PickItem, DispatchRecord

class BinInventoryInline(admin.TabularInline):
    model = BinInventory
    extra = 0

@admin.register(Bin)
class BinAdmin(admin.ModelAdmin):
    list_display = ('code', 'shelf', 'bin_type')
    inlines = [BinInventoryInline]

@admin.register(PickingTask)
class PickingTaskAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'warehouse', 'status', 'picker')

@admin.register(DispatchRecord)
class DispatchRecordAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'status', 'rider_id', 'pickup_otp')