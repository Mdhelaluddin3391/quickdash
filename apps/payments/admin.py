from django.contrib import admin
from .models import PaymentIntent, Refund

@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    """
    Payment Intent ko Admin Panel mein dikhane ke liye.
    """
    list_display = ('id', 'order', 'gateway_order_id', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__id', 'gateway_order_id', 'gateway_payment_id')
    
    # In fields ko admin mein badla nahi ja sakta
    readonly_fields = (
        'id', 
        'order', 
        'gateway_order_id', 
        'gateway_payment_id', 
        'amount', 
        'status', 
        'created_at', 
        'updated_at'
    )

    def has_add_permission(self, request):
        # Admin se naya payment banana allow nahi hai
        return False

    def has_delete_permission(self, request, obj=None):
        # Payments ko delete nahi karna hai
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """
    Refund requests ko Admin Panel mein dikhane ke liye.
    """
    list_display = ('id', 'order', 'payment', 'amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__id', 'payment__gateway_payment_id', 'gateway_refund_id')
    
    readonly_fields = (
        'id', 
        'payment', 
        'order', 
        'pick_item_id', 
        'reason', 
        'amount', 
        'gateway_refund_id', 
        'created_at', 
        'processed_at'
    )

    def has_add_permission(self, request):
        # Admin se naya refund banana allow nahi hai
        return False