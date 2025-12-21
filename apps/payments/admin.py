# apps/payments/admin.py
from django.contrib import admin
from .models import Payment, PaymentIntent, Refund


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "user",
        "payment_method",
        "amount",
        "currency",
        "status",
        "transaction_id",
        "gateway_order_id",
        "created_at",
    )
    list_filter = ("payment_method", "status", "created_at")
    search_fields = ("order__id", "transaction_id", "gateway_order_id")


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "gateway_order_id",
        "amount",
        "currency",
        "status",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("gateway_order_id", "order__id")


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "payment",
        "order",
        "amount",
        "status",
        "gateway_refund_id",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("id", "payment__gateway_order_id", "gateway_refund_id")
