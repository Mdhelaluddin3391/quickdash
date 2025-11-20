from django.contrib import admin
from .models import Payment, PaymentIntent, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'status', 'payment_method', 'amount', 'created_at')
    search_fields = ('order__id', 'transaction_id', 'gateway_order_id')


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'gateway_order_id', 'status', 'amount', 'created_at')
    search_fields = ('gateway_order_id',)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'payment', 'order', 'amount', 'status', 'created_at')
    search_fields = ('id', 'payment__gateway_order_id')