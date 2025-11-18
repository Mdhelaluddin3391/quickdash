# apps/orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem, OrderTimeline

class OrderItemInline(admin.TabularInline):
    """
    Yeh Order admin page ke andar items ko inline (usi page par)
    dikhane mein madad karega.
    """
    model = OrderItem
    extra = 0  # Default mein koi extra khaali form nahi dikhayega
    readonly_fields = ('sku', 'sku_name_snapshot', 'unit_price', 'quantity', 'total_price')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderTimelineInline(admin.TabularInline):
    """
    Yeh Order admin page ke andar order ki history dikhayega.
    """
    model = OrderTimeline
    extra = 0
    readonly_fields = ('timestamp', 'status', 'notes')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Order model ke liye Admin panel configuration.
    """
    list_display = (
        'id', 
        'customer', 
        'status', 
        'payment_status', 
        'final_amount', 
        'warehouse', 
        'created_at'
    )
    list_filter = ('status', 'payment_status', 'warehouse', 'created_at')
    search_fields = ('id', 'customer__phone', 'payment_gateway_order_id')
    
    # Order page ke andar items aur timeline dikhane ke liye
    inlines = [OrderItemInline, OrderTimelineInline]
    
    # In fields ko admin mein badla nahi ja sakta (readonly)
    readonly_fields = (
        'id', 
        'customer', 
        'warehouse', 
        'total_amount', 
        'discount_amount', 
        'final_amount',
        'payment_gateway_order_id',
        'packer', 
        'rider', 
        'created_at', 
        'updated_at', 
        'delivered_at'
    )

    def has_add_permission(self, request):
        return False


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    (Optional) OrderItem model ko alag se dekhne ke liye.
    """
    list_display = ('order', 'sku', 'sku_name_snapshot', 'quantity', 'total_price')
    search_fields = ('order__id', 'sku__sku_code', 'sku_name_snapshot')