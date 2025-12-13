from django.contrib import admin
from .models import (
    Order, OrderItem, OrderTimeline, 
    Coupon, Cart, CartItem, OrderCancellation
)

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



class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('sku', 'quantity', 'unit_price', 'total_price', 'added_at')
    can_delete = False

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'total_amount', 'updated_at')
    search_fields = ('customer__phone', 'customer__email')
    readonly_fields = ('customer', 'created_at', 'updated_at')
    inlines = [CartItemInline]
    
    def has_add_permission(self, request):
        return False  # Carts are system-generated

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_value', 'is_percentage', 'valid_to', 'active', 'times_used')
    list_filter = ('active', 'is_percentage')
    search_fields = ('code',)
    fieldsets = (
        ('Coupon Details', {
            'fields': ('code', 'active')
        }),
        ('Value', {
            'fields': ('discount_value', 'is_percentage', 'min_purchase_amount')
        }),
        ('Validity', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('Stats', {
            'fields': ('times_used',),
            'classes': ('collapse',)
        })
    )

@admin.register(OrderCancellation)
class OrderCancellationAdmin(admin.ModelAdmin):
    list_display = ('order', 'reason_code', 'cancelled_by', 'created_at')
    list_filter = ('cancelled_by',)
    search_fields = ('order__id', 'reason')
    readonly_fields = ('order', 'created_at', 'cancelled_by_user')