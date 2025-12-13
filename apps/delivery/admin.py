from django.contrib import admin
from .models import (
    DeliveryTask, RiderEarning, RiderPayout, 
    RiderCashDeposit, RiderApplication  # <-- Imported RiderApplication
)

@admin.register(DeliveryTask)
class DeliveryTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "rider",
        "status",
        "created_at",
        "picked_up_at",
        "delivered_at",
    )
    list_filter = ("status", "created_at", "rider")
    search_fields = ("id", "order__id", "rider__rider_code")

    readonly_fields = (
        "id",
        "dispatch_record_id",
        "order",
        "rider",
        "pickup_otp",
        "delivery_otp",
        "created_at",
        "accepted_at",
        "picked_up_at",
        "delivered_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(RiderEarning)
class RiderEarningAdmin(admin.ModelAdmin):
    list_display = (
        "rider",
        "delivery_task",
        "total_earning",
        "status",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("rider__rider_code", "order_id_str")
    readonly_fields = (
        "rider",
        "delivery_task",
        "order_id_str",
        "base_fee",
        "tip",
        "total_earning",
        "created_at",
    )

    def has_add_permission(self, request):
        return False


@admin.register(RiderPayout)
class RiderPayoutAdmin(admin.ModelAdmin):
    list_display = ("rider", "amount_paid", "transaction_ref", "created_at")
    search_fields = ("rider__rider_code", "transaction_ref")


@admin.register(RiderCashDeposit)
class RiderCashDepositAdmin(admin.ModelAdmin):
    list_display = ("rider", "amount", "status", "created_at")
    list_filter = ("status",)


@admin.register(RiderApplication)
class RiderApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('full_name', 'phone')
    list_editable = ('status',)
    
    actions = ['approve_application', 'reject_application']

    @admin.action(description='Approve selected applications')
    def approve_application(self, request, queryset):
        queryset.update(status='APPROVED')

    @admin.action(description='Reject selected applications')
    def reject_application(self, request, queryset):
        queryset.update(status='REJECTED')