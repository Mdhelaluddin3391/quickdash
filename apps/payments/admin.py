from django.contrib import admin
from .models import Payment, PaymentIntent, WebhookLog

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'order', 'amount', 'status', 'method', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('transaction_id', 'order__id')
    readonly_fields = ('gateway_response',)

@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ('gateway_order_id', 'order', 'amount', 'status')
    search_fields = ('gateway_order_id', 'order__id')

@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('event_id', 'provider', 'is_processed', 'created_at')
    list_filter = ('is_processed', 'created_at')
    readonly_fields = ('payload',)