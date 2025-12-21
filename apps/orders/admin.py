import json
from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import (
    Order, OrderItem, OrderTimeline, 
    Coupon, Cart, CartItem, OrderCancellation
)

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('sku', 'sku_name_snapshot', 'unit_price', 'quantity', 'total_price')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OrderTimelineInline(admin.TabularInline):
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
    Refactored Order Admin to match new model structure.
    """
    list_display = (
        'order_id',          # Changed from 'id' to human-readable order_id
        'customer', 
        'status', 
        'payment_status', 
        'final_amount',      # Updated from total_amount
        'warehouse', 
        'created_at'
    )
    list_filter = ('status', 'payment_status', 'warehouse', 'created_at')
    search_fields = ('order_id', 'id', 'customer__phone', 'payment_gateway_order_id')
    
    inlines = [OrderItemInline, OrderTimelineInline]
    
    # Show ALL fields in read-only mode
    readonly_fields = (
        'id', 
        'order_id',
        'customer', 
        'warehouse', 
        'final_amount',           # Replaces total_amount
        'payment_gateway_order_id',
        'status',
        'payment_status',
        'formatted_delivery_address', # Custom method for JSON
        'formatted_metadata',         # Custom method for JSON
        'delivery_city',
        'delivery_pincode',
        'delivery_lat',
        'delivery_lng',
        'created_at', 
        'updated_at', 
        'confirmed_at',
        'cancelled_at',
        'delivered_at'
    )

    fieldsets = (
        ('Order Details', {
            'fields': ('order_id', 'id', 'status', 'customer', 'warehouse')
        }),
        ('Financials', {
            'fields': ('final_amount', 'payment_status', 'payment_gateway_order_id')
        }),
        ('Delivery Info', {
            'fields': ('formatted_delivery_address', 'delivery_city', 'delivery_pincode', 'delivery_lat', 'delivery_lng')
        }),
        ('System Data', {
            'fields': ('formatted_metadata', 'created_at', 'updated_at', 'confirmed_at', 'delivered_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False

    # --- Custom Methods to Display JSON Fields Prettily ---
    
    def formatted_delivery_address(self, obj):
        """Displays delivery_address_json as formatted HTML"""
        if not obj.delivery_address_json:
            return "-"
        # Convert dict to a pretty HTML string
        content = json.dumps(obj.delivery_address_json, indent=2)
        return mark_safe(f"<pre>{content}</pre>")
    
    formatted_delivery_address.short_description = "Delivery Address Snapshot"

    def formatted_metadata(self, obj):
        """Displays metadata as formatted HTML"""
        if not obj.metadata:
            return "-"
        content = json.dumps(obj.metadata, indent=2)
        return mark_safe(f"<pre>{content}</pre>")
    
    formatted_metadata.short_description = "Metadata (Debug Info)"


# ... (Rest of the file remains unchanged: OrderItemAdmin, CartAdmin, etc.)
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
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
        return False

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