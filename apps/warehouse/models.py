# apps/warehouse/models.py
import uuid
import logging
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from apps.catalog.models import SKU

logger = logging.getLogger(__name__)

import logging
logger = logging.getLogger(__name__)

# =========================================================
# 1. PHYSICAL STRUCTURE
# =========================================================

class Warehouse(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    address = models.TextField()
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Zone(models.Model):
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="zones",
    )
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10)

    class Meta:
        unique_together = ("warehouse", "code")

    def __str__(self):
        return f"{self.warehouse.code}-{self.code}"

class Aisle(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="aisles")
    code = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.zone.code}-{self.code}"

class Shelf(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="shelves")
    code = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.aisle.code}-{self.code}"

class Bin(models.Model):
    # [FIX] Renamed 'sshelf' to 'shelf' to match unique_together constraint
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="bins")

    # Optional direct zone link if needed for legacy, but hierarchy prefers shelf
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="bins_direct", null=True, blank=True)
    
    bin_code = models.CharField(max_length=20, unique=True, db_index=True)
    capacity = models.FloatField(default=100.0)

    def __str__(self):
        return self.bin_code

    class Meta:
        unique_together = ('shelf', 'bin_code')


class BinInventory(models.Model):
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="inventory")
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=0)
    reserved_qty = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("bin", "sku")

    @property
    def available_qty(self) -> int:
        return self.qty - self.reserved_qty

    def __str__(self):
        return f"{self.bin.bin_code} / {self.sku.sku_code} -> {self.qty} ({self.reserved_qty} reserved)"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        INWARD = "INWARD", "Inward (GRN)"
        OUTWARD = "OUTWARD", "Outward (Dispatch)"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment (Lost/Found)"
        RESERVE = "RESERVE", "Order Reservation"
        PUTAWAY = "PUTAWAY", "Putaway"
        ROLLBACK = "ROLLBACK", "Rollback"
        CYCLE_COUNT = "CYCLE_COUNT", "Cycle Count"

    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, null=True, blank=True)
    qty_change = models.IntegerField()
    movement_type = models.CharField(max_length=32, choices=MovementType.choices)
    reference_id = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["sku", "warehouse"]),
            models.Index(fields=["movement_type", "timestamp"]),
        ]


# =========================================================
# 2. TASKS (PICK → PACK → DISPATCH)
# =========================================================

class PickingTask(models.Model):
    class TaskStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    order_id = models.CharField(max_length=50, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="picking_tasks",
    )
    status = models.CharField(
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"PickTask {self.id} / Order {self.order_id}"


class PickItem(models.Model):
    task = models.ForeignKey(
        PickingTask,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    qty_to_pick = models.PositiveIntegerField()
    picked_qty = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.task.order_id} - {self.sku.sku_code} ({self.picked_qty}/{self.qty_to_pick})"


class PackingTask(models.Model):
    class PackStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PACKING = "PACKING", "Packing"
        PACKED = "PACKED", "Packed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    picking_task = models.OneToOneField(
        PickingTask,
        on_delete=models.CASCADE,
        related_name="packing_task",
    )
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="packing_tasks",
    )
    status = models.CharField(
        max_length=30,
        choices=PackStatus.choices,
        default=PackStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PackTask {self.id} / Order {self.picking_task.order_id}"


class DispatchRecord(models.Model):
    class DispatchStatus(models.TextChoices):
        READY = "ready", "Ready"
        ASSIGNED = "assigned", "Rider Assigned"
        HANDED_OVER = "handed_over", "Handed Over to Rider"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    packing_task = models.OneToOneField(
        PackingTask,
        on_delete=models.CASCADE,
        related_name="dispatch_record",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=128, db_index=True)
    pickup_otp = models.CharField(max_length=10, blank=True, null=True)
    status = models.CharField(
        max_length=30,
        choices=DispatchStatus.choices,
        default=DispatchStatus.READY,
        db_index=True,
    )
    # link to delivery/rider world by ID (string) to avoid circular imports
    rider_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of rider assigned by delivery service",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dispatch {self.id} / Order {self.order_id} ({self.status})"


# =========================================================
# 3. EXCEPTIONS (SKIPS / SHORT-PICK / FC)
# =========================================================

class PickSkip(models.Model):
    task = models.ForeignKey(
        PickingTask,
        on_delete=models.CASCADE,
        related_name="skips",
    )
    pick_item = models.ForeignKey(
        PickItem,
        on_delete=models.CASCADE,
        related_name="skips",
    )
    skipped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )
    reason = models.CharField(max_length=255)
    is_resolved = models.BooleanField(default=False)
    reopen_after_scan = models.BooleanField(
        default=False,
        help_text="If true, picker can try to re-scan after resolution.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Skip {self.id} - {self.reason[:20]}"


class ShortPickIncident(models.Model):
    skip = models.OneToOneField(PickSkip, on_delete=models.CASCADE)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )
    short_picked_qty = models.IntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class FulfillmentCancel(models.Model):
    pick_item = models.ForeignKey(
        PickItem,
        on_delete=models.CASCADE,
        related_name="fc_records",
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    reason = models.CharField(max_length=255)
    refund_initiated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


# =========================================================
# 4. INBOUND (GRN & PUTAWAY)
# =========================================================

class GRN(models.Model):
    class GrnStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        RECEIVED = "received", "Received"
        PUTAWAY_COMPLETE = "putaway_complete", "Putaway Complete"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="grns",
    )
    grn_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=GrnStatus.choices,
        default=GrnStatus.PENDING,
        db_index=True,
    )
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
    )

    def __str__(self):
        return f"GRN {self.grn_number} ({self.warehouse.code})"


class GRNItem(models.Model):
    grn = models.ForeignKey(
        GRN,
        on_delete=models.CASCADE,
        related_name="items",
    )
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    expected_qty = models.IntegerField()
    received_qty = models.IntegerField(default=0)


class PutawayTask(models.Model):
    class PutawayStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn = models.OneToOneField(
        GRN,
        on_delete=models.CASCADE,
        related_name="putaway_task",
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    putaway_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="putaway_tasks",
    )
    status = models.CharField(
        max_length=30,
        choices=PutawayStatus.choices,
        default=PutawayStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class PutawayItem(models.Model):
    task = models.ForeignKey(
        PutawayTask,
        on_delete=models.CASCADE,
        related_name="items",
    )
    grn_item = models.ForeignKey(GRNItem, on_delete=models.CASCADE)
    placed_qty = models.IntegerField(default=0)
    placed_bin = models.ForeignKey(
        Bin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )


# =========================================================
# 5. CYCLE COUNT
# =========================================================

class CycleCountTask(models.Model):
    class CcStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.CASCADE,
        related_name="cc_tasks",
    )
    task_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cc_tasks",
    )
    status = models.CharField(
        max_length=30,
        choices=CcStatus.choices,
        default=CcStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class CycleCountItem(models.Model):
    task = models.ForeignKey(
        CycleCountTask,
        on_delete=models.CASCADE,
        related_name="items",
    )
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    expected_qty = models.IntegerField()
    counted_qty = models.IntegerField(null=True, blank=True)
    adjusted = models.BooleanField(default=False)


# =========================================================
# 6. IDEMPOTENCY
# =========================================================

class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True, db_index=True)
    route = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64, blank=True)
    response_status = models.SmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return self.expires_at < timezone.now()

    class Meta:
        verbose_name_plural = "Idempotency Keys"


# =========================================================
# 7. AUTO STOCK SYNC TO CENTRAL INVENTORY
# =========================================================

# def sync_inventory_stock(warehouse_id, sku_id):
#     """
#     Calculates total available stock across ALL bins for a specific SKU in a Warehouse,
#     and updates the central 'InventoryStock' (apps.inventory) used by cart/search.
#     """
#     from apps.inventory.models import InventoryStock  # local import to avoid circulars

#     try:
#         with transaction.atomic():
#             totals = BinInventory.objects.filter(
#                 bin__zone__warehouse_id=warehouse_id,
#                 sku_id=sku_id,
#             ).aggregate(
#                 total_qty=Sum("qty"),
#                 total_reserved=Sum("reserved_qty"),
#             )
#             qty = totals["total_qty"] or 0
#             reserved = totals["total_reserved"] or 0
#             available = max(0, qty - reserved)

#             stock, _ = InventoryStock.objects.select_for_update().get_or_create(
#                 warehouse_id=warehouse_id,
#                 sku_id=sku_id,
#                 defaults={"available_qty": 0, "reserved_qty": 0},
#             )
#             stock.available_qty = available
#             stock.reserved_qty = reserved
#             stock.save()

#             logger.info(
#                 "SYNC: SKU %s in WH %s -> avail=%s reserved=%s",
#                 sku_id,
#                 warehouse_id,
#                 available,
#                 reserved,
#             )
#     except Exception:
#         logger.exception("Stock sync failed for warehouse=%s sku=%s", warehouse_id, sku_id)


# @receiver([post_save, post_delete], sender=BinInventory)
# def on_bin_inventory_change(sender, instance, **kwargs):
#     """
#     Whenever BinInventory changes, update central InventoryStock.
#     """
#     warehouse_id = instance.bin.zone.warehouse_id
#     sku_id = instance.sku_id
#     sync_inventory_stock(warehouse_id, sku_id)
