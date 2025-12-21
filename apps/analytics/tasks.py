# apps/analytics/tasks.py
import logging
from datetime import date

from celery import shared_task
from django.utils import timezone

from .services import (
    compute_daily_sales_summary,
    compute_warehouse_kpi_snapshot,
    compute_rider_kpi_snapshot,
    compute_sku_analytics_daily,
    compute_inventory_snapshot_daily,
)

logger = logging.getLogger(__name__)


def _resolve_day(day_str: str | None) -> date:
    if day_str:
        return timezone.datetime.strptime(day_str, "%Y-%m-%d").date()
    return timezone.localdate()


@shared_task
def run_daily_analytics_for_date(day_str: str | None = None):
    """
    Single orchestration task to run all daily aggregations.
    Typically scheduled at night via Celery beat.
    """
    day = _resolve_day(day_str)
    logger.info("Starting daily analytics for %s", day)

    compute_daily_sales_summary(day)
    compute_warehouse_kpi_snapshot(day)
    compute_rider_kpi_snapshot(day)
    compute_sku_analytics_daily(day)
    compute_inventory_snapshot_daily(day)

    logger.info("Completed daily analytics for %s", day)
