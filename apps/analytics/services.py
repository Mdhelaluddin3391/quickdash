# apps/analytics/services.py
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from apps.warehouse.models import PickingTask, DispatchRecord
from apps.orders.models import Order, OrderItem
from apps.warehouse.models import Warehouse
from apps.delivery.models import DeliveryTask
from apps.inventory.models import InventoryStock
from apps.catalog.models import SKU
from apps.accounts.models import RiderProfile
from apps.payments.models import Payment
from .models import (
    DailySalesSummary,
    WarehouseKPISnapshot,
    RiderKPISnapshot,
    SKUAnalyticsDaily,
    InventorySnapshotDaily,
)

logger = logging.getLogger(__name__)


def _start_end_of_day(day: date):
    """
    Given a date, return its start & end datetime in current timezone.
    """
    # Django ka `make_aware` helper use karein jo ZoneInfo compatible hai
    start_naive = timezone.datetime.combine(day, timezone.datetime.min.time())
    end_naive = timezone.datetime.combine(day, timezone.datetime.max.time())
    
    start = timezone.make_aware(start_naive)
    end = timezone.make_aware(end_naive)
    
    return start, end


@transaction.atomic
def compute_daily_sales_summary(day: date | None = None) -> DailySalesSummary:
    if day is None:
        day = timezone.localdate()

    start, end = _start_end_of_day(day)

    qs = Order.objects.filter(created_at__gte=start, created_at__lte=end)

    total_orders = qs.count()
    total_paid_orders = qs.filter(payment_status="paid").count()
    total_cancelled_orders = qs.filter(status__in=["cancelled", "cancelled_fc"]).count()

    total_revenue = qs.filter(payment_status="paid").aggregate(
        s=Sum("final_amount")
    )["s"] or Decimal("0.00")

    # Refund amount from Payments or Refunds
    refund_sum = (
        Payment.objects.filter(
            order__in=qs,
            status__in=["REFUNDED", "REFUND_INITIATED"],
        ).aggregate(s=Sum("amount"))["s"]
        or Decimal("0.00")
    )

    avg_order_value = (
        total_revenue / total_paid_orders if total_paid_orders > 0 else Decimal("0.00")
    )

    obj, _ = DailySalesSummary.objects.update_or_create(
        date=day,
        defaults={
            "total_orders": total_orders,
            "total_paid_orders": total_paid_orders,
            "total_cancelled_orders": total_cancelled_orders,
            "total_revenue": total_revenue,
            "total_refund_amount": refund_sum,
            "avg_order_value": avg_order_value,
        },
    )

    logger.info("Computed DailySalesSummary for %s", day)
    return obj


# apps/analytics/services.py

# ... (imports remain same)

@transaction.atomic
def compute_warehouse_kpi_snapshot(day: date | None = None) -> None:
    if day is None:
        day = timezone.localdate()
    start, end = _start_end_of_day(day)

    for wh in Warehouse.objects.filter(is_active=True):
        # 1. Base Order Counts
        o_qs = Order.objects.filter(
            warehouse=wh,
            created_at__gte=start,
            created_at__lte=end,
        )
        orders_created = o_qs.count()
        orders_dispatched = o_qs.filter(status="dispatched").count()
        orders_delivered = o_qs.filter(status="delivered").count()
        
        # 2. Calculate Pick Duration from PickingTasks
        # Filter tasks completed today
        pick_tasks = PickingTask.objects.filter(
            warehouse=wh,
            status='COMPLETED',
            completed_at__gte=start,
            completed_at__lte=end,
            started_at__isnull=False
        )
        
        total_pick_seconds = 0
        pick_count = 0
        for task in pick_tasks:
            duration = (task.completed_at - task.started_at).total_seconds()
            if duration > 0:
                total_pick_seconds += duration
                pick_count += 1
        
        avg_pick_time = int(total_pick_seconds / pick_count) if pick_count > 0 else 0

        # 3. Calculate Pack Duration (Time from Pick Complete -> Dispatch Ready)
        # Using DispatchRecord
        dispatches = DispatchRecord.objects.filter(
            warehouse=wh,
            created_at__gte=start,
            created_at__lte=end
        ).select_related('picking_task')
        
        total_pack_seconds = 0
        pack_count = 0
        for d in dispatches:
            if d.picking_task and d.picking_task.completed_at:
                duration = (d.created_at - d.picking_task.completed_at).total_seconds()
                if duration > 0:
                    total_pack_seconds += duration
                    pack_count += 1
                    
        avg_pack_time = int(total_pack_seconds / pack_count) if pack_count > 0 else 0

        # Update Snapshot
        WarehouseKPISnapshot.objects.update_or_create(
            date=day,
            warehouse=wh,
            defaults={
                "orders_created": orders_created,
                "orders_dispatched": orders_dispatched,
                "orders_delivered": orders_delivered,
                "orders_cancelled": o_qs.filter(status__in=["cancelled"]).count(),
                "avg_pick_time_seconds": avg_pick_time,
                "avg_pack_time_seconds": avg_pack_time,
                "avg_dispatch_to_delivery_seconds": 0, # Requires DeliveryTask calculation
                "short_pick_incidents": 0,
                "full_cancellations": 0,
            },
        )

    logger.info("Computed WarehouseKPISnapshot for %s", day)

@transaction.atomic
def compute_rider_kpi_snapshot(day: date | None = None) -> None:
    if day is None:
        day = timezone.localdate()
    start, end = _start_end_of_day(day)

    # assuming DeliveryTask has created_at, delivered_at, status
    tasks = DeliveryTask.objects.filter(
        created_at__gte=start,
        created_at__lte=end,
    ).select_related("rider")

    riders = RiderProfile.objects.all()

    for rider in riders:
        rider_tasks = tasks.filter(rider=rider)
        if not rider_tasks.exists():
            continue

        tasks_assigned = rider_tasks.count()
        tasks_completed = rider_tasks.filter(
            status=DeliveryTask.DeliveryStatus.DELIVERED
        ).count()
        tasks_failed = rider_tasks.filter(
            status__in=[DeliveryTask.DeliveryStatus.FAILED, DeliveryTask.DeliveryStatus.CANCELLED]
        ).count()

        # average delivery time
        delivery_duration = ExpressionWrapper(
            F("delivered_at") - F("picked_up_at"), output_field=DurationField()
        )
        agg = rider_tasks.filter(
            status=DeliveryTask.DeliveryStatus.DELIVERED
        ).aggregate(avg_del=Avg(delivery_duration))

        def to_seconds(d):
            return int(d.total_seconds()) if d else 0

        avg_delivery_time = to_seconds(agg["avg_del"])

        from apps.delivery.models import RiderEarning

        total_earnings = (
            RiderEarning.objects.filter(
                rider=rider,
                created_at__gte=start,
                created_at__lte=end,
            ).aggregate(s=Sum("total_earning"))["s"]
            or Decimal("0.00")
        )

        RiderKPISnapshot.objects.update_or_create(
            date=day,
            rider=rider,
            defaults={
                "tasks_assigned": tasks_assigned,
                "tasks_completed": tasks_completed,
                "tasks_failed": tasks_failed,
                "total_earnings": total_earnings,
                "avg_delivery_time_seconds": avg_delivery_time,
            },
        )

    logger.info("Computed RiderKPISnapshot for %s", day)


@transaction.atomic
def compute_sku_analytics_daily(day: date | None = None) -> None:
    if day is None:
        day = timezone.localdate()
    start, end = _start_end_of_day(day)

    # assuming OrderItem model exists in apps.orders.models
    from apps.orders.models import OrderItem

    items_qs = OrderItem.objects.filter(
        order__created_at__gte=start,
        order__created_at__lte=end,
        order__status__in=["dispatched", "delivered"],
    ).select_related("sku")

    # aggregate by SKU
    rows = items_qs.values("sku_id").annotate(
        qty=Sum("quantity"),
        revenue=Sum("total_price"),
        orders_count=Count("order_id", distinct=True),
    )

    for row in rows:
        sku_id = row["sku_id"]
        quantity_sold = row["qty"] or 0
        gross_revenue = row["revenue"] or Decimal("0.00")
        orders_count = row["orders_count"] or 0

        avg_price = (
            gross_revenue / quantity_sold if quantity_sold > 0 else Decimal("0.00")
        )

        SKUAnalyticsDaily.objects.update_or_create(
            date=day,
            sku_id=sku_id,
            defaults={
                "quantity_sold": quantity_sold,
                "gross_revenue": gross_revenue,
                "avg_selling_price": avg_price,
                "orders_count": orders_count,
                # refunds/refunded_quantity can be added from Refund model if needed
            },
        )

    logger.info("Computed SKUAnalyticsDaily for %s", day)


@transaction.atomic
def compute_inventory_snapshot_daily(day: date | None = None) -> None:
    if day is None:
        day = timezone.localdate()

    # For now: snapshot of current InventoryStock as-of now (EOD).
    stocks = InventoryStock.objects.select_related("warehouse", "sku")

    for s in stocks:
        InventorySnapshotDaily.objects.update_or_create(
            date=day,
            warehouse=s.warehouse,
            sku=s.sku,
            defaults={
                "closing_available_qty": s.available_qty,
                "closing_reserved_qty": s.reserved_qty,
            },
        )

    logger.info("Computed InventorySnapshotDaily for %s", day)
