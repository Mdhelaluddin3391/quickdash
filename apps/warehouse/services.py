# apps/warehouse/services.py

from django.db import transaction
from django.db.models import F, OuterRef, Subquery, Sum, IntegerField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db.models import F
from apps.inventory.models import (
    InventoryStock, BinInventory, StockMovement, SKU
)

from apps.warehouse.models import (
    Bin, Warehouse, PickingTask, PickItem, PackingTask,
    PackingItem, DispatchRecord, PickSkip, ShortPickIncident,
    FulfillmentCancel, GRN, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem
)


# =========================================================
# EXCEPTIONS
# =========================================================
class OutOfStockError(Exception):
    pass


# =========================================================
# RESERVATION
# =========================================================
def allocate_from_bins(warehouse_id, sku_id, qty, reference_type=None, reference_id=None):
    allocations = []
    remaining = qty

    qs = BinInventory.objects.select_for_update().filter(
        sku_id=sku_id,
        bin__shelf__aisle__zone__warehouse_id=warehouse_id,
        qty__gt=F("reserved_qty"),
    ).select_related("bin").order_by(
        "-bin__preferred_sku", "-qty"
    )

    for bi in qs:
        available = bi.qty - bi.reserved_qty
        if available <= 0:
            continue

        take = min(available, remaining)

        bi.reserved_qty = F("reserved_qty") + take
        bi.save(update_fields=["reserved_qty"])

        allocations.append({"bin_id": bi.bin_id, "allocated": take})

        StockMovement.objects.create(
            sku_id=sku_id,
            warehouse_id=warehouse_id,
            bin_id=bi.bin_id,
            change_type="reserve",
            delta_qty=-take,
            reference_type=reference_type,
            reference_id=reference_id,
        )

        remaining -= take
        if remaining == 0:
            break

    if remaining > 0:
        raise OutOfStockError(
            f"Could not allocate {qty} of SKU {sku_id} in warehouse {warehouse_id}"
        )

    return allocations


def reserve_stock_for_order(order_id, warehouse_id, items):
    sku_ids = [it["sku_id"] for it in items]

    with transaction.atomic():
        inv_rows = InventoryStock.objects.select_for_update().filter(
            warehouse_id=warehouse_id,
            sku_id__in=sku_ids
        )

        inv_map = {row.sku_id: row for row in inv_rows}

        # check availability
        for it in items:
            r = inv_map.get(it["sku_id"])
            if not r or r.available_qty < it["qty"]:
                raise OutOfStockError(
                    f"SKU {it['sku_id']} insufficient in warehouse {warehouse_id}"
                )

        allocations_summary = {}

        # reserve items
        for it in items:
            r = inv_map[it["sku_id"]]

            InventoryStock.objects.filter(pk=r.pk).update(
                available_qty=F("available_qty") - it["qty"],
                reserved_qty=F("reserved_qty") + it["qty"],
            )

            allocs = allocate_from_bins(
                warehouse_id,
                it["sku_id"],
                it["qty"],
                reference_type="order",
                reference_id=str(order_id),
            )

            allocations_summary[it["sku_id"]] = allocs

        return allocations_summary


# =========================================================
# PICKING TASK CREATION
# =========================================================
def create_picking_task_from_reservation(order_id, warehouse_id, allocations):
    with transaction.atomic():
        pt = PickingTask.objects.create(
            order_id=str(order_id),
            warehouse_id=warehouse_id,
            status="pending"
        )

        for sku_id, alloc_list in allocations.items():
            merged = {}

            # merge per bin
            for a in alloc_list:
                merged[a["bin_id"]] = merged.get(a["bin_id"], 0) + a["allocated"]

            # create PickItems safely
            for bin_id, qty in merged.items():
                PickItem.objects.create(
                    task=pt,
                    sku_id=sku_id,
                    bin_id=bin_id,
                    qty=qty
                )

        return pt


def assign_picker(task_id, picker_user):
    pt = PickingTask.objects.get(id=task_id)
    pt.picker = picker_user
    pt.status = "assigned"
    pt.started_at = timezone.now()
    pt.save(update_fields=["picker", "status", "started_at"])
    return pt


# =========================================================
# SCAN PICK (SAFE, NON-NEGATIVE)
# =========================================================
def scan_pick(task_id, pick_item_id, bin_code, sku_code, qty_scanned, scanned_by_user):
    with transaction.atomic():
        pi = PickItem.objects.select_for_update().select_related(
            "bin", "sku", "task"
        ).get(pk=pick_item_id, task_id=task_id)

        if pi.bin.code != bin_code:
            raise ValueError("Bin code mismatch")

        if pi.sku.sku_code != sku_code:
            raise ValueError("SKU code mismatch")

        remaining = pi.qty - pi.picked_qty
        if remaining <= 0:
            raise ValueError("Already fully picked")

        if qty_scanned <= 0:
            raise ValueError("Invalid qty")

        take = min(qty_scanned, remaining)

        # ---- SAFE INVENTORY UPDATES ----
        bi = BinInventory.objects.select_for_update().get(
            bin_id=pi.bin_id,
            sku_id=pi.sku_id
        )

        current_qty = bi.qty
        current_reserved = bi.reserved_qty

        if current_qty < take:
            raise ValueError("Insufficient physical stock in bin")

        new_qty = current_qty - take
        new_reserved = current_reserved - take
        if new_reserved < 0:
            new_reserved = 0

        bi.qty = new_qty
        bi.reserved_qty = new_reserved
        bi.save(update_fields=["qty", "reserved_qty"])

        inv = InventoryStock.objects.select_for_update().get(
            warehouse_id=pi.task.warehouse_id,
            sku_id=pi.sku_id
        )

        inv.reserved_qty = max(inv.reserved_qty - take, 0)
        inv.save(update_fields=["reserved_qty"])

        # stock movement
        StockMovement.objects.create(
            sku_id=pi.sku_id,
            warehouse_id=pi.task.warehouse_id,
            bin_id=pi.bin_id,
            change_type="pick",
            delta_qty=-take,
            reference_type="order_pick",
            reference_id=pi.task.order_id
        )

        pi.picked_qty = F("picked_qty") + take
        pi.scanned_at = timezone.now()
        pi.save(update_fields=["picked_qty", "scanned_at"])
        pi.refresh_from_db()

        # complete task if possible
        task = pi.task
        if all(it.picked_qty >= it.qty for it in task.items.all()):
            task.status = "completed"
            task.completed_at = timezone.now()
            task.save(update_fields=["status", "completed_at"])
        else:
            task.status = "in_progress"
            task.save(update_fields=["status"])

        skipped_to_try = PickSkip.objects.filter(
            pick_item__task=task,
            reopen_after_scan=True,
            resolved=False
        ).exists()

        return pi, {"skipped_to_try_again": skipped_to_try}


# =========================================================
# SKIP / SHORT-PICK / FULFILLMENT CANCEL
# =========================================================
def mark_pickitem_skipped(task_id, pick_item_id, picker_user, reason=None):
    with transaction.atomic():
        pi = PickItem.objects.select_for_update().get(pk=pick_item_id, task_id=task_id)

        if pi.picked_qty >= pi.qty:
            raise ValueError("Already fully picked")

        if hasattr(pi, "skip") and not pi.skip.resolved:
            return pi.skip

        skip = PickSkip.objects.create(
            pick_item=pi,
            picker=picker_user,
            reason=reason or "",
            reopen_after_scan=False
        )

        task = pi.task
        if any(it.picked_qty > 0 for it in task.items.all()):
            task.status = "in_progress"
        else:
            task.status = "partial"

        task.save(update_fields=["status"])
        return skip


def resolve_skip_as_shortpick(pick_skip: PickSkip, created_by_user=None, note=""):
    with transaction.atomic():
        spi = ShortPickIncident.objects.create(
            pick_item=pick_skip.pick_item,
            created_by=created_by_user,
            note=note
        )

        pick_skip.resolved = True
        pick_skip.resolution_note = "short-pick"
        pick_skip.resolved_by = created_by_user
        pick_skip.resolved_at = timezone.now()
        pick_skip.save()

        return spi


def admin_fulfillment_cancel(pick_item: PickItem, admin_user, reason=""):
    if hasattr(pick_item, "fulfillment_cancel"):
        raise ValueError("Already fulfillment canceled")

    with transaction.atomic():
        fc = FulfillmentCancel.objects.create(
            pick_item=pick_item,
            admin=admin_user,
            reason=reason
        )

        remaining = pick_item.qty - pick_item.picked_qty

        if remaining > 0:
            
            # --- Step 1: Original Bin se Stock Debit karein ---
            # Hum maan rahe hain ki 'remaining' quantity us bin se kho gayi hai.
            try:
                bi = BinInventory.objects.select_for_update().get(
                    bin_id=pick_item.bin_id,
                    sku_id=pick_item.sku_id
                )
                
                # Physical 'qty' aur 'reserved_qty' dono ko kam karein
                bi.qty = F("qty") - remaining
                bi.reserved_qty = F("reserved_qty") - remaining
                bi.save(update_fields=["qty", "reserved_qty"])

            except BinInventory.DoesNotExist:
                # Aisa hona nahi chahiye, lekin agar ho toh log karein
                logger.error(f"BinInventory missing for FC on pick_item {pick_item.id}")
                pass


            # --- Step 2: Warehouse ke Total Stock ko Update karein ---
            try:
                inv = InventoryStock.objects.select_for_update().get(
                    warehouse_id=pick_item.task.warehouse_id,
                    sku_id=pick_item.sku_id
                )

                # Sirf 'reserved_qty' ko kam karein.
                # Hum 'available_qty' ko wapas ADD NAHI kar rahe.
                # Isse warehouse ka total sellable stock 'remaining' amount se kam ho jaata hai.
                inv.reserved_qty = max(inv.reserved_qty - remaining, 0)
                inv.save(update_fields=["reserved_qty"])
            
            except InventoryStock.DoesNotExist:
                logger.error(f"InventoryStock missing for FC on pick_item {pick_item.id}")
                pass

            
            # --- Step 3: Stock Movement ko 'lost' ki tarah log karein ---
            StockMovement.objects.create(
                sku_id=pick_item.sku_id,
                warehouse_id=pick_item.task.warehouse_id,
                bin_id=pick_item.bin_id,
                change_type="fc_lost",  # Pehle yeh 'fc_return' tha
                delta_qty=-remaining,   # Hum stock ghata rahe hain
                reference_type="fulfillment_cancel",
                reference_id=str(pick_item.task.order_id)
            )

        return fc


# =========================================================
# PACKING
# =========================================================
def create_packing_task_from_picking(picking_task_id):
    with transaction.atomic():
        pt = PickingTask.objects.get(id=picking_task_id)

        if pt.status != "completed":
            raise ValueError("Picking not completed")

        pack = PackingTask.objects.create(
            picking_task=pt,
            status="pending"
        )

        for it in pt.items.all():
            PackingItem.objects.create(
                packing_task=pack,
                sku=it.sku,
                qty=it.picked_qty
            )

        return pack


def complete_packing(packing_task_id, packer_user, package_label=None):
    with transaction.atomic():
        pack = PackingTask.objects.select_for_update().get(id=packing_task_id)

        if pack.status == "packed":
            return pack

        pack.packer = packer_user
        pack.status = "packed"
        pack.packed_at = timezone.now()

        if package_label:
            pack.package_label = package_label

        pack.save(update_fields=["packer", "status", "packed_at", "package_label"])

        for item in pack.items.all():
            StockMovement.objects.create(
                sku_id=item.sku_id,
                warehouse_id=pack.picking_task.warehouse_id,
                bin_id=None,
                change_type="pack",
                delta_qty=0,
                reference_type="order_pack",
                reference_id=pack.picking_task.order_id
            )

        dr = DispatchRecord.objects.create(
            order_id=pack.picking_task.order_id,
            warehouse_id=pack.picking_task.warehouse_id,
            packing_task=pack,
            status="ready"
        )

        return pack, dr


# =========================================================
# DISPATCH
# =========================================================
def assign_dispatch(dispatch_id, courier_name, courier_id=None):
    with transaction.atomic():
        dr = DispatchRecord.objects.select_for_update().get(id=dispatch_id)
        dr.courier = courier_name
        dr.courier_id = courier_id
        dr.status = "assigned"
        dr.assigned_at = timezone.now()
        dr.save(update_fields=["courier", "courier_id", "status", "assigned_at"])
        return dr


def mark_picked_up(dispatch_id):
    with transaction.atomic():
        dr = DispatchRecord.objects.select_for_update().get(id=dispatch_id)
        dr.status = "picked_up"
        dr.picked_up_at = timezone.now()
        dr.save(update_fields=["status", "picked_up_at"])
        return dr


def mark_delivered(dispatch_id):
    with transaction.atomic():
        dr = DispatchRecord.objects.select_for_update().get(id=dispatch_id)
        dr.status = "delivered"
        dr.delivered_at = timezone.now()
        dr.save(update_fields=["status", "delivered_at"])
        return dr


# =========================================================
# PUTAWAY
# =========================================================
def create_grn_and_putaway(warehouse_id, grn_no, received_items, created_by=None, metadata=None):
    with transaction.atomic():
        grn = GRN.objects.create(
            grn_no=grn_no,
            warehouse_id=warehouse_id,
            created_by=created_by,
            metadata=metadata or {}
        )

        task = PutawayTask.objects.create(
            grn=grn,
            warehouse_id=warehouse_id
        )

        for it in received_items:
            sku_id = it["sku_id"]
            qty = it["qty"]

            preferred = Bin.objects.filter(
                shelf__aisle__zone__warehouse_id=warehouse_id,
                preferred_sku_id=sku_id
            ).first()

            if preferred:
                suggested = preferred
            else:
                bins = Bin.objects.filter(
                    shelf__aisle__zone__warehouse_id=warehouse_id
                )

                sub = (
                    BinInventory.objects
                    .filter(bin_id=OuterRef("pk"))
                    .values("bin")
                    .annotate(s=Sum("qty"))
                    .values("s")[:1]
                )

                bins = bins.annotate(
                    total_qty=Coalesce(
                        Subquery(sub, output_field=IntegerField()),
                        0
                    )
                )

                suggested = bins.order_by("total_qty").first()

            PutawayItem.objects.create(
                putaway_task=task,
                sku_id=sku_id,
                qty=qty,
                suggested_bin=suggested
            )

        return grn, task


def place_putaway_item(putaway_task_id, putaway_item_id, bin_id, qty, performed_by):
    with transaction.atomic():
        pai = PutawayItem.objects.select_for_update().get(
            pk=putaway_item_id,
            putaway_task_id=putaway_task_id
        )

        if qty <= 0 or qty + pai.placed_qty > pai.qty:
            raise ValueError("Invalid qty")

        bi, created = BinInventory.objects.select_for_update().get_or_create(
            bin_id=bin_id,
            sku_id=pai.sku_id,
            defaults={"qty": 0, "reserved_qty": 0}
        )

        bi.qty = bi.qty + qty
        bi.save(update_fields=["qty"])

        inv, _ = InventoryStock.objects.select_for_update().get_or_create(
            warehouse_id=pai.putaway_task.warehouse_id,
            sku_id=pai.sku_id,
            defaults={"available_qty": 0, "reserved_qty": 0}
        )

        inv.available_qty = inv.available_qty + qty
        inv.save(update_fields=["available_qty"])

        StockMovement.objects.create(
            sku_id=pai.sku_id,
            warehouse_id=pai.putaway_task.warehouse_id,
            bin_id=bin_id,
            change_type="putaway",
            delta_qty=qty,
            reference_type="grn",
            reference_id=str(pai.putaway_task.grn_id)
        )

        pai.placed_bin_id = bin_id
        pai.placed_qty = pai.placed_qty + qty
        pai.save(update_fields=["placed_bin", "placed_qty"])

        return pai


# =========================================================
# CYCLE COUNT
# =========================================================
def create_cycle_count(warehouse_id, created_by, sample_bins=None):
    with transaction.atomic():
        task = CycleCountTask.objects.create(
            warehouse_id=warehouse_id,
            created_by=created_by,
            status="pending"
        )

        bins = Bin.objects.filter(
            shelf__aisle__zone__warehouse_id=warehouse_id
        )

        if sample_bins:
            bins = bins.filter(id__in=sample_bins)
        else:
            bins = bins[:50]

        for b in bins:
            for bi in BinInventory.objects.filter(bin=b):
                CycleCountItem.objects.create(
                    cycle_task=task,
                    bin=b,
                    sku=bi.sku,
                    expected_qty=bi.qty
                )

        return task


def record_cycle_count_item(cycle_task_id, bin_id, sku_id, counted_qty, counted_by):
    with transaction.atomic():
        item = CycleCountItem.objects.select_for_update().get(
            cycle_task_id=cycle_task_id,
            bin_id=bin_id,
            sku_id=sku_id
        )

        item.counted_qty = counted_qty
        item.counted_at = timezone.now()

        if counted_qty != item.expected_qty:
            delta = counted_qty - item.expected_qty

            bi = BinInventory.objects.select_for_update().get(
                bin_id=bin_id,
                sku_id=sku_id
            )

            bi.qty = bi.qty + delta
            bi.save(update_fields=["qty"])

            inv = InventoryStock.objects.select_for_update().get(
                warehouse_id=item.cycle_task.warehouse_id,
                sku_id=sku_id
            )

            inv.available_qty = inv.available_qty + delta
            inv.save(update_fields=["available_qty"])

            StockMovement.objects.create(
                sku_id=sku_id,
                warehouse_id=item.cycle_task.warehouse_id,
                bin_id=bin_id,
                change_type="cycle_adjust",
                delta_qty=delta,
                reference_type="cycle_count",
                reference_id=str(item.cycle_task_id)
            )

            item.adjusted = True
            item.adjusted_by = counted_by
            item.adjusted_at = timezone.now()
            item.adjustment_note = f"Adjusted by cycle count delta={delta}"

        item.save()
        return item
