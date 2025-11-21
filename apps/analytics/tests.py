# apps/analytics/tests.py
from django.test import TestCase
from django.utils import timezone
from decimal import Decimal

from apps.orders.models import Order
from apps.warehouse.models import Warehouse
from apps.catalog.models import SKU, Category, Brand
from apps.accounts.models import User
from .models import DailySalesSummary
from .services import compute_daily_sales_summary


class DailySalesSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="+910000000000", password="test")
        self.wh = Warehouse.objects.create(
            name="WH1",
            code="WH-1",
            address="Test",
            is_active=True,
        )
        cat = Category.objects.create(name="TestCat")
        brand = Brand.objects.create(name="TestBrand")
        self.sku = SKU.objects.create(
            sku_code="TEST-SKU",
            name="Test SKU",
            category=cat,
            brand=brand,
            sale_price=Decimal("100.00"),
            cost_price=Decimal("80.00"),
        )

        self.order = Order.objects.create(
            customer=self.user,
            warehouse=self.wh,
            status="delivered",
            payment_status="paid",
            final_amount=Decimal("150.00"),
        )

    def test_compute_daily_sales_summary_creates_row(self):
        day = timezone.localdate()
        summary = compute_daily_sales_summary(day)
        self.assertIsInstance(summary, DailySalesSummary)
        self.assertEqual(summary.total_orders, 1)
        self.assertEqual(summary.total_paid_orders, 1)
        self.assertEqual(summary.total_revenue, Decimal("150.00"))
