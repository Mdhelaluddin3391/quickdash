# apps/warehouse/services.py
from django.db import transaction
from django.utils import timezone

from apps.inventory.models import InventoryStock, BinInventory, StockMovement, SKU
from apps.warehouse.models import (
    Warehouse, Bin,
    PickingTask, PickItem,
    PackingTask, PackingItem,
    DispatchRecord,
    PickSkip, ShortPickIncident, FulfillmentCancel,
    GRN, PutawayTask, PutawayItem,
    CycleCountTask, CycleCountItem,
)
from .exceptions import OutOfStockError
from .utils.warehouse_selector import select_best_warehouse


# ================== Reservation ================== #
from channels.layers import get_channel_layer
layer = get_channel_layer()

async def broadcast(event):
    await layer.group_send(
        "wms_realtime",
        {
            "type": "wms_event",
            "data": event,
        }
    )



@transaction.atomic
def reserve_stock_for_order(order_id, warehouse_id, items):
    """
    items = [ { "sku_id": <uuid>, "qty": int }, ... ]
    Returns allocations:
        { sku_id: [ {"bin_id": <uuid>, "qty": int}, ... ], ... }
    """
    allocations = {}
    warehouse = Warehouse.objects.select_for_update().get(id=warehouse_id)

    for it in items:
        sku_id = it["sku_id"]
        qty_needed = int(it["qty"])

        inv = InventoryStock.objects.select_for_update().get(
            warehouse=warehouse, sku_id=sku_id
        )
        if inv.available_qty < qty_needed:
            raise OutOfStockError(
                f"Not enough stock for SKU {sku_id} in warehouse {warehouse.code}"
            )

        # bin-level reservation
        remaining = qty_needed
        bin_qs = (
            BinInventory.objects.select_for_update()
            .filter(bin__shelf__aisle__zone__warehouse=warehouse, sku_id=sku_id)
            .order_by("-qty")
        )

        allocations[sku_id] = []
        for bi in bin_qs:
            if remaining <= 0:
                break
            take = min(remaining, bi.qty - bi.reserved_qty)
            if take <= 0:
                continue

            bi.reserved_qty += take
            bi.save(update_fields=["reserved_qty"])

            StockMovement.objects.create(
                sku_id=sku_id,
                warehouse=warehouse,
                bin=bi.bin,
                change_type="reserve",
                delta_qty=-take,
                reference_type="order",
                reference_id=str(order_id),
            )

            allocations[sku_id].append({"bin_id": bi.bin_id, "qty": take})
            remaining -= take

        if remaining > 0:
            # rollback via transaction
            raise OutOfStockError(
                f"Not enough bin-level stock for SKU {sku_id} in warehouse {warehouse.code}"
            )

        # warehouse-level reservation
        inv.available_qty -= qty_needed
        inv.reserved_qty += qty_needed
        inv.save(update_fields=["available_qty", "reserved_qty"])

    return allocations


@transaction.atomic
def create_picking_task_from_reservation(order_id, warehouse_id, allocations, picker=None):
    """
    allocations from reserve_stock_for_order.
    """
    task = PickingTask.objects.create(
        order_id=str(order_id),
        warehouse_id=warehouse_id,
        picker=picker,
        status="pending",
    )

    for sku_id, alloc_list in allocations.items():
        for alloc in alloc_list:
            PickItem.objects.create(
                task=task,
                sku_id=sku_id,
                bin_id=alloc["bin_id"],
                qty=alloc["qty"],
            )

    return task


# ================== Picking ================== #

@transaction.atomic
def scan_pick(task_id, bin_id, sku_id, qty, scanned_by=None):
    """
    Scan an item while picking.
    """
    qty = int(qty)

    item = PickItem.objects.select_for_update().get(
        task_id=task_id, bin_id=bin_id, sku_id=sku_id
    )

    if item.picked_qty + qty > item.qty:
        raise ValueError("Picked quantity exceeds required quantity")

    item.picked_qty += qty
    item.scanned_at = timezone.now()
    item.save(update_fields=["picked_qty", "scanned_at"])

    task = item.task
    if task.status == "pending":
        task.status = "in_progress"
        task.started_at = timezone.now()

    # if all items fulfilled -> complete
    all_done = not task.items.filter(picked_qty__lt=models.F("qty")).exists()
    if all_done:
        task.status = "completed"
        task.completed_at = timezone.now()
    task.save()

    return item


@transaction.atomic
def create_pick_skip(pick_item_id, picker, reason=""):
    pick_item = PickItem.objects.select_for_update().get(id=pick_item_id)
    skip, created = PickSkip.objects.get_or_create(
        pick_item=pick_item,
        defaults={"picker": picker, "reason": reason},
    )
    if not created:
        skip.reason = reason
        skip.reopened = True
        skip.save(update_fields=["reason", "reopened"])
    return skip


@transaction.atomic
def record_short_pick(pick_item_id, reported_by, note=""):
    pick_item = PickItem.objects.select_for_update().get(id=pick_item_id)
    incident, created = ShortPickIncident.objects.get_or_create(
        pick_item=pick_item,
        defaults={"reported_by": reported_by, "note": note},
    )
    if not created:
        incident.note = note
        incident.status = "open"
        incident.reported_by = reported_by
        incident.reported_at = timezone.now()
        incident.save()
    return incident


@transaction.atomic
def create_fulfillment_cancel(pick_item_id, admin, reason=""):
    pick_item = PickItem.objects.select_for_update().get(id=pick_item_id)
    fc, created = FulfillmentCancel.objects.get_or_create(
        pick_item=pick_item,
        defaults={"admin": admin, "reason": reason},
    )
    if not created:
        fc.reason = reason
        fc.admin = admin
        fc.save(update_fields=["reason", "admin"])
    return fc


# ================== Packing & Dispatch ================== #

@transaction.atomic
def create_packing_task_from_picking(picking_task_id, packer=None):
    picking_task = PickingTask.objects.select_for_update().get(id=picking_task_id)
    if hasattr(picking_task, "packing_task"):
        return picking_task.packing_task

    pack_task = PackingTask.objects.create(
        picking_task=picking_task,
        packer=packer,
        status="pending",
    )

    for pitem in picking_task.items.all():
        PackingItem.objects.create(
            packing_task=pack_task,
            sku=pitem.sku,
            qty=pitem.qty,
            packed_qty=0,
        )

    return pack_task


@transaction.atomic
def complete_packing(packing_task_id, packer=None, total_weight_kg=None):
    pack_task = PackingTask.objects.select_for_update().get(id=packing_task_id)
    if packer:
        pack_task.packer = packer
    pack_task.status = "packed"
    pack_task.completed_at = timezone.now()
    if total_weight_kg is not None:
        pack_task.total_weight_kg = total_weight_kg
    pack_task.save()

    dispatch, _ = DispatchRecord.objects.get_or_create(
        packing_task=pack_task,
        defaults={
            "order_id": pack_task.picking_task.order_id,
            "warehouse": pack_task.picking_task.warehouse,
            "status": "ready",
        },
    )
    return dispatch


# ================== Inbound: GRN + Putaway ================== #

@transaction.atomic
def create_grn_and_putaway(warehouse_id, grn_no, items, created_by=None):
    """
    items = [ {"sku_id": <uuid>, "qty": int}, ... ]
    """
    wh = Warehouse.objects.select_for_update().get(id=warehouse_id)
    grn = GRN.objects.create(
        warehouse=wh,
        grn_no=grn_no,
        created_by=created_by,
        status="received",
    )
    task = PutawayTask.objects.create(
        grn=grn,
        warehouse=wh,
        assigned_to=created_by,
        status="pending",
    )
    for it in items:
        PutawayItem.objects.create(
            task=task,
            sku_id=it["sku_id"],
            expected_qty=int(it["qty"]),
        )
    return grn, task


@transaction.atomic
def place_putaway_item(task_id, bin_id, sku_id, qty, placed_by=None):
    qty = int(qty)
    task = PutawayTask.objects.select_for_update().get(id=task_id)
    item = PutawayItem.objects.select_for_update().get(
        task=task, sku_id=sku_id
    )
    bin_obj = Bin.objects.get(id=bin_id)

    item.bin = bin_obj
    item.placed_qty += qty
    item.placed_at = timezone.now()
    item.save()

    # Update bin inventory
    bi, _ = BinInventory.objects.select_for_update().get_or_create(
        bin=bin_obj,
        sku_id=sku_id,
        defaults={"qty": 0, "reserved_qty": 0},
    )
    bi.qty += qty
    bi.save(update_fields=["qty"])

    # Update warehouse inventory
    inv, _ = InventoryStock.objects.select_for_update().get_or_create(
        warehouse=task.warehouse,
        sku_id=sku_id,
        defaults={"available_qty": 0, "reserved_qty": 0},
    )
    inv.available_qty += qty
    inv.save(update_fields=["available_qty"])

    StockMovement.objects.create(
        sku_id=sku_id,
        warehouse=task.warehouse,
        bin=bin_obj,
        change_type="putaway",
        delta_qty=qty,
        reference_type="grn",
        reference_id=str(task.grn_id),
    )

    # if all items fully placed -> complete task & grn
    all_done = not task.items.filter(placed_qty__lt=models.F("expected_qty")).exists()
    if all_done:
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save(update_fields=["status", "completed_at"])
        task.grn.status = "completed"
        task.grn.save(update_fields=["status"])

    return item


# ================== Cycle count / Audit ================== #

@transaction.atomic
def create_cycle_count(warehouse_id, created_by=None, sample_bins=None):
    """
    sample_bins: list of bin_ids to include; if None -> all bins in warehouse.
    """
    wh = Warehouse.objects.get(id=warehouse_id)
    task = CycleCountTask.objects.create(
        warehouse=wh,
        created_by=created_by,
    )

    bin_qs = Bin.objects.filter(
        shelf__aisle__zone__warehouse=wh,
        is_active=True,
    )
    if sample_bins:
        bin_qs = bin_qs.filter(id__in=sample_bins)

    for bi in BinInventory.objects.filter(bin__in=bin_qs).select_related("bin", "sku"):
        CycleCountItem.objects.create(
            cycle_task=task,
            bin=bi.bin,
            sku=bi.sku,
            expected_qty=bi.qty,
        )

    return task


@transaction.atomic
def record_cycle_count_item(task_id, bin_id, sku_id, counted_qty, counted_by=None):
    counted_qty = int(counted_qty)

    item = CycleCountItem.objects.select_for_update().get(
        cycle_task_id=task_id,
        bin_id=bin_id,
        sku_id=sku_id,
    )
    item.counted_qty = counted_qty
    item.counted_at = timezone.now()

    if counted_qty != item.expected_qty and not item.adjusted:
        delta = counted_qty - item.expected_qty

        bi = BinInventory.objects.select_for_update().get(
            bin_id=bin_id,
            sku_id=sku_id,
        )
        bi.qty += delta
        bi.save(update_fields=["qty"])

        inv = InventoryStock.objects.select_for_update().get(
            warehouse=item.cycle_task.warehouse,
            sku_id=sku_id,
        )
        inv.available_qty += delta
        inv.save(update_fields=["available_qty"])

        StockMovement.objects.create(
            sku_id=sku_id,
            warehouse=item.cycle_task.warehouse,
            bin_id=bin_id,
            change_type="cycle_adjust",
            delta_qty=delta,
            reference_type="cycle_count",
            reference_id=str(task_id),
        )

        item.adjusted = True
        item.adjusted_by = counted_by
        item.adjusted_at = timezone.now()
        item.adjustment_note = f"Adjusted by cycle count delta={delta}"

    item.save()
    return item
