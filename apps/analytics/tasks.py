# apps/analytics/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Avg, Count, F, DurationField
from django.db.models.functions import Coalesce
from datetime import timedelta

# Models import karein
from apps.orders.models import Order
from apps.warehouse.models import Warehouse
from apps.analytics.models import DailyKPI
import logging

logger = logging.getLogger(__name__)

@shared_task
def generate_daily_kpi_report():
    """
    Yeh task har raat (e.g., 12:05 AM) chalna chahiye.
    Yeh pichle din (Yesterday) ka data calculate karke DailyKPI table mein bharega.
    """
    # 1. Date decide karein (Yesterday)
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    logger.info(f"Starting Daily KPI calculation for date: {yesterday}")

    # 2. Saare active warehouses fetch karein
    warehouses = Warehouse.objects.filter(is_active=True)

    for warehouse in warehouses:
        try:
            # Warehouse specific orders filter karein
            orders_qs = Order.objects.filter(
                warehouse=warehouse,
                created_at__date=yesterday
            )

            # --- METRICS CALCULATION ---
            
            # A. Total Orders & Revenue
            total_orders = orders_qs.count()
            
            # Agar koi order nahi hai, toh revenue 0.00 maano
            agg_data = orders_qs.aggregate(
                revenue=Coalesce(Sum('final_amount'), 0.00)
            )
            total_revenue = agg_data['revenue']

            # B. Fulfillment Rate (Delivered vs Total)
            delivered_orders_qs = orders_qs.filter(status='delivered')
            delivered_count = delivered_orders_qs.count()

            if total_orders > 0:
                fulfillment_rate = (delivered_count / total_orders) * 100
            else:
                fulfillment_rate = 100.00 # Agar order hi nahi aaye, toh rate 100% ya 0% (Business Logic)

            # C. Avg Delivery Time (Minutes)
            # Delivered orders ka (delivered_at - created_at) ka average nikalo
            avg_time_data = delivered_orders_qs.annotate(
                delivery_duration=F('delivered_at') - F('created_at')
            ).aggregate(
                avg_duration=Avg('delivery_duration')
            )
            
            avg_duration = avg_time_data['avg_duration']
            avg_minutes = 0
            if avg_duration:
                avg_minutes = int(avg_duration.total_seconds() / 60)

            # --- SAVE TO DB ---
            
            # DailyKPI record create ya update karein
            kpi, created = DailyKPI.objects.update_or_create(
                date=yesterday,
                warehouse=warehouse,
                defaults={
                    'total_orders': total_orders,
                    'total_revenue': total_revenue,
                    'fulfillment_rate': round(fulfillment_rate, 2),
                    'avg_delivery_time_min': avg_minutes,
                    # Inventory discrepancy abhi 0 rakhenge (Inventory module se link karna baki hai)
                    'inventory_discrepancy_count': 0 
                }
            )
            
            logger.info(f"KPI generated for {warehouse.code}: Orders={total_orders}, Rev={total_revenue}")

        except Exception as e:
            logger.error(f"Failed to generate KPI for warehouse {warehouse.code}: {e}")

    return f"KPI Report generated for {yesterday}"