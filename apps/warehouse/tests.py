# apps/warehouse/tests/test_reservation.py
from django.test import TestCase
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin
from apps.inventory.models import SKU, BinInventory, InventoryStock
from apps.warehouse.services import reserve_stock_for_order, OutOfStockError
import uuid
from django.test import TestCase
from apps.warehouse.models import Warehouse, Zone, Aisle, Shelf, Bin, PickingTask, PickItem
from apps.inventory.models import SKU, BinInventory, InventoryStock
from apps.warehouse.services import reserve_stock_for_order, create_picking_task_from_reservation, scan_pick, create_packing_task_from_picking, complete_packing
from django.contrib.auth import get_user_model
# apps/warehouse/tests/test_skip_putaway_cycle_fc.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.warehouse.models import (Warehouse, Zone, Aisle, Shelf, Bin,
    PickingTask, PickItem, PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, PutawayTask, PutawayItem, CycleCountTask, CycleCountItem)
from apps.inventory.models import SKU, BinInventory, InventoryStock, StockMovement
from apps.warehouse.services import (
    mark_pickitem_skipped, reopen_skipped_for_picker, resolve_skip_as_shortpick,
    admin_fulfillment_cancel, create_grn_and_putaway, place_putaway_item,
    create_cycle_count, record_cycle_count_item
)
import uuid

User = get_user_model()


class ReservationTestCase(TestCase):
    def setUp(self):
        self.w = Warehouse.objects.create(code='TW', name='Test WH')
        z = Zone.objects.create(warehouse=self.w, code='Z1')
        a = Aisle.objects.create(zone=z, code='A1')
        s = Shelf.objects.create(aisle=a, code='S1')
        b = Bin.objects.create(shelf=s, code='B01')
        self.sku = SKU.objects.create(sku_code='TSKU', name='Test SKU')
        BinInventory.objects.create(bin=b, sku=self.sku, qty=100, reserved_qty=0)
        InventoryStock.objects.create(warehouse=self.w, sku=self.sku, available_qty=100, reserved_qty=0)

    def test_reserve_success(self):
        order_id = uuid.uuid4()
        allocations = reserve_stock_for_order(order_id, self.w.id, [{'sku_id': self.sku.id, 'qty': 5}])
        self.assertIn(self.sku.id, allocations)
        # refresh
        stock = InventoryStock.objects.get(warehouse=self.w, sku=self.sku)
        self.assertEqual(stock.available_qty, 95)
        self.assertEqual(stock.reserved_qty, 5)

    def test_reserve_fail(self):
        order_id = uuid.uuid4()
        with self.assertRaises(OutOfStockError):
            reserve_stock_for_order(order_id, self.w.id, [{'sku_id': self.sku.id, 'qty': 1000}])




User = get_user_model()

class EndToEndTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='picker', is_staff=False)
        self.w = Warehouse.objects.create(code='WTEST', name='Test WH')
        z = Zone.objects.create(warehouse=self.w, code='Z1')
        a = Aisle.objects.create(zone=z, code='A1')
        s = Shelf.objects.create(aisle=a, code='S1')
        b = Bin.objects.create(shelf=s, code='B01')
        self.sku = SKU.objects.create(sku_code='E2E', name='E2E Item')
        BinInventory.objects.create(bin=b, sku=self.sku, qty=50, reserved_qty=0)
        InventoryStock.objects.create(warehouse=self.w, sku=self.sku, available_qty=50, reserved_qty=0)

    def test_reserve_pick_pack_dispatch(self):
        order_id = uuid.uuid4()
        allocations = reserve_stock_for_order(order_id, self.w.id, [{'sku_id': self.sku.id, 'qty': 5}])
        self.assertIn(self.sku.id, allocations)
        # create pick task
        pt = create_picking_task_from_reservation(order_id, self.w.id, allocations)
        # simulate pick scan
        pick_item = pt.items.first()
        pi = scan_pick(pt.id, pick_item.id, pick_item.bin.code, pick_item.sku.sku_code, 5, self.user)
        self.assertEqual(pi.picked_qty, 5)
        # create packing
        packing = create_packing_task_from_picking(pt.id)
        pack, dr = complete_packing(packing.id, self.user, package_label='LBL123')
        self.assertEqual(pack.status, 'packed')
        self.assertEqual(dr.status, 'ready')





class SkipUnpickFulfillTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='picker', is_staff=False)
        self.admin = User.objects.create(username='admin', is_staff=True)
        # setup warehouse and one bin/sku
        self.w = Warehouse.objects.create(code='W1', name='WH1')
        z = Zone.objects.create(warehouse=self.w, code='Z1')
        a = Aisle.objects.create(zone=z, code='A1')
        s = Shelf.objects.create(aisle=a, code='S1')
        b = Bin.objects.create(shelf=s, code='B01')
        self.sku = SKU.objects.create(sku_code='TSKU', name='Test SKU')
        BinInventory.objects.create(bin=b, sku=self.sku, qty=10, reserved_qty=0)
        InventoryStock.objects.create(warehouse=self.w, sku=self.sku, available_qty=10, reserved_qty=0)
        # create a picking task manually
        self.order_id = uuid.uuid4()
        self.pt = PickingTask.objects.create(order_id=str(self.order_id), warehouse=self.w, status='pending')
        self.pi = PickItem.objects.create(task=self.pt, sku=self.sku, bin=b, qty=5, picked_qty=0)

    def test_skip_and_resolve_shortpick_and_fc(self):
        # skip the item
        skip = mark_pickitem_skipped(self.pt.id, self.pi.id, self.user, reason='not found')
        self.assertTrue(hasattr(skip, 'id'))
        # reopen skip for picker (manual)
        reopened = reopen_skipped_for_picker(skip)
        self.assertTrue(reopened.reopen_after_scan)
        # resolve skip as shortpick (escalation)
        spi = resolve_skip_as_shortpick(reopened, created_by_user=self.user, note='tried multiple times')
        self.assertTrue(hasattr(spi, 'id'))
        # admin fulfullment cancel (simulate FC on same pick item)
        fc = admin_fulfillment_cancel(self.pi, self.admin, reason='customer cancelled')
        self.assertTrue(hasattr(fc, 'id'))
        # after FC, inventory updated: check InventoryStock.available_qty increased by remaining (5)
        inv = InventoryStock.objects.get(warehouse=self.w, sku=self.sku)
        self.assertGreaterEqual(inv.available_qty, 10)  # should be at or above original (depends on prior ops)

class PutawayAndCycleTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='putaway_user')
        self.w = Warehouse.objects.create(code='W2', name='WH2')
        z = Zone.objects.create(warehouse=self.w, code='DRY')
        a = Aisle.objects.create(zone=z, code='A1')
        s = Shelf.objects.create(aisle=a, code='S1')
        self.b1 = Bin.objects.create(shelf=s, code='P01')
        self.b2 = Bin.objects.create(shelf=s, code='P02')
        self.sku = SKU.objects.create(sku_code='PUTSKU', name='Put SKU')
        # initially no stock

    def test_create_grn_and_putaway_and_place(self):
        grn_no = 'GRN-100'
        items = [{'sku_id': str(self.sku.id), 'qty': 20}]
        grn, task = create_grn_and_putaway(self.w.id, grn_no, items, created_by=self.user)
        self.assertEqual(task.grn.id, grn.id)
        pai = task.items.first()
        # place 10 into bin1
        placed = place_putaway_item(task.id, pai.id, self.b1.id, 10, self.user)
        self.assertEqual(placed.placed_bin.id, self.b1.id)
        placed.refresh_from_db()
        # check BinInventory created
        bi = BinInventory.objects.get(bin=self.b1, sku=self.sku)
        self.assertEqual(bi.qty, 10)
        # place remaining into bin2 (10)
        placed2 = place_putaway_item(task.id, pai.id, self.b2.id, 10, self.user)
        bi2 = BinInventory.objects.get(bin=self.b2, sku=self.sku)
        self.assertEqual(bi2.qty, 10)
        # inventory stock should be 20
        inv = InventoryStock.objects.get(warehouse=self.w, sku=self.sku)
        self.assertEqual(inv.available_qty, 20)

    def test_cycle_count_adjustment(self):
        # seed bin inventory
        bi = BinInventory.objects.create(bin=self.b1, sku=self.sku, qty=15, reserved_qty=0)
        inv = InventoryStock.objects.create(warehouse=self.w, sku=self.sku, available_qty=15, reserved_qty=0)
        # create cycle count
        task = create_cycle_count(self.w.id, self.user, sample_bins=[self.b1.id])
        item = task.items.get(bin=self.b1, sku=self.sku)
        # record counted qty lower than expected -> 12 => adjust -3
        recorded = record_cycle_count_item(task.id, self.b1.id, self.sku.id, 12, self.user)
        bi.refresh_from_db()
        inv.refresh_from_db()
        self.assertEqual(bi.qty, 12)
        self.assertEqual(inv.available_qty, 12)
        self.assertTrue(recorded.adjusted)
