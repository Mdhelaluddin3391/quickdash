# apps/inventory/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.catalog.models import Category, Brand, SKU
from apps.warehouse.models import Warehouse
from .models import InventoryStock, InventoryHistory
from .tasks import update_inventory_stock_task
from .services import find_best_warehouse_for_items

User = get_user_model()


class InventoryTaskTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Dairy")
        self.brand = Brand.objects.create(name="Amul")
        self.sku = SKU.objects.create(
            sku_code="MILK-1L-AMUL",
            name="Amul Milk 1L",
            category=self.cat,
            brand=self.brand,
            sale_price="60.00",
            cost_price="50.00",
        )
        self.wh = Warehouse.objects.create(
            name="WH1",
            code="WH-1",
            address="Test",
            is_active=True,
        )

    def test_update_inventory_creates_stock_and_history(self):
        # Call task synchronously
        update_inventory_stock_task(
            sku_id=self.sku.id,
            warehouse_id=self.wh.id,
            delta_available=10,
            delta_reserved=0,
            reference="TEST-GRN",
            change_type="putaway",
        )

        stock = InventoryStock.objects.get(
            warehouse=self.wh,
            sku=self.sku,
        )
        self.assertEqual(stock.available_qty, 10)
        self.assertEqual(stock.reserved_qty, 0)

        hist = InventoryHistory.objects.filter(
            warehouse=self.wh,
            sku=self.sku,
        ).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.delta_available, 10)
        self.assertEqual(hist.available_after, 10)
        self.assertEqual(hist.change_type, "putaway")


class InventoryRoutingTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Dairy")
        self.brand = Brand.objects.create(name="Amul")
        self.sku = SKU.objects.create(
            sku_code="MILK-1L-AMUL",
            name="Amul Milk 1L",
            category=self.cat,
            brand=self.brand,
            sale_price="60.00",
            cost_price="50.00",
        )
        self.wh1 = Warehouse.objects.create(
            name="WH1",
            code="WH-1",
            address="Test 1",
            is_active=True,
        )
        self.wh2 = Warehouse.objects.create(
            name="WH2",
            code="WH-2",
            address="Test 2",
            is_active=True,
        )

        InventoryStock.objects.create(
            warehouse=self.wh1,
            sku=self.sku,
            available_qty=5,
            reserved_qty=0,
        )
        InventoryStock.objects.create(
            warehouse=self.wh2,
            sku=self.sku,
            available_qty=20,
            reserved_qty=0,
        )

    def test_find_best_warehouse_prefers_higher_stock(self):
        order_items = [{"sku_id": self.sku.id, "qty": 3}]
        wh = find_best_warehouse_for_items(order_items)
        self.assertIsNotNone(wh)
        self.assertEqual(wh.id, self.wh2.id)
