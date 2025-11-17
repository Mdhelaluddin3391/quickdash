# apps/warehouse/models.py
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
# FIX: SKU ko 'inventory' app se import kiya
from apps.inventory.models import SKU


class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Zone(models.Model):
    id = models.AutoField(primary_key=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="zones")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = ("warehouse", "code")

    def __str__(self):
        return f"{self.warehouse.code}/{self.code}"


class Aisle(models.Model):
    id = models.AutoField(primary_key=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="aisles")
    code = models.CharField(max_length=50)

    class Meta:
        unique_together = ("zone", "code")

    def __str__(self):
        return f"{self.zone}/{self.code}"


class Shelf(models.Model):
    id = models.AutoField(primary_key=True)
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="shelves")
    code = models.CharField(max_length=50)

    class Meta:
        unique_together = ("aisle", "code")

    def __str__(self):
        return f"{self.aisle}/{self.code}"


class Bin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="bins")
    code = models.CharField(max_length=50)
    bin_type = models.CharField(max_length=20, default="default")  # ambient / cold / frozen
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("shelf", "code")
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return f"{self.shelf}/{self.code}"

# =========================================================
# FIX: BinInventory model ko 'inventory' app se yahaan move kiya
# =========================================================
class BinInventory(models.Model):
    id = models.BigAutoField(primary_key=True)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name='inventory')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='bin_inventories')
    qty = models.IntegerField(default=0)         # total qty physically present
    reserved_qty = models.IntegerField(default=0) # qty reserved for orders (not yet picked)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bin', 'sku')
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['bin']),
        ]

    def available_qty(self):
        return self.qty - self.reserved_qty

    def __str__(self):
        return f"{self.bin} / {self.sku.sku_code} => {self.qty} (res {self.reserved_qty})"

# =========================================================
# FIX: StockMovement model ko 'inventory' app se yahaan move kiya
# =========================================================
class StockMovement(models.Model):
    id = models.BigAutoField(primary_key=True)
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, null=True, on_delete=models.SET_NULL)
    change_type = models.CharField(max_length=50)  # sale, adjustment, return, purchase
    delta_qty = models.IntegerField()
    reference_type = models.CharField(max_length=50, null=True, blank=True)  # order, purchase_order
    reference_id = models.CharField(max_length=128, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['sku']), models.Index(fields=['warehouse']), models.Index(fields=['created_at'])]


# --------- Picking / Packing / Dispatch --------- #

PICK_STATUS_CHOICES = [
    ("pending", "pending"),
    ("in_progress", "in_progress"),
    ("completed", "completed"),
    ("cancelled", "cancelled"),
]

PACK_STATUS_CHOICES = [
    ("pending", "pending"),
    ("in_progress", "in_progress"),
    ("packed", "packed"),
    ("cancelled", "cancelled"),
]

DISPATCH_STATUS_CHOICES = [
    ("ready", "ready"),
    ("assigned", "assigned"),
    ("picked_up", "picked_up"),
    ("delivered", "delivered"),
    ("failed", "failed"),
]


class PickingTask(models.Model):
    """
    One picking task = 1 order in one warehouse.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=128, db_index=True)  # external order id
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="picking_tasks")
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="picking_tasks",
    )
    status = models.CharField(max_length=30, choices=PICK_STATUS_CHOICES, default="pending", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    def __str__(self):
        return f"PickTask {self.order_id} ({self.status})"


class PickItem(models.Model):
    """
    A single SKU in a picking task, from a specific bin.
    """
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(PickingTask, related_name="items", on_delete=models.CASCADE)
    sku = models.ForeignKey("inventory.SKU", on_delete=models.CASCADE)
    bin = models.ForeignKey("Bin", on_delete=models.CASCADE)
    qty = models.IntegerField()
    picked_qty = models.IntegerField(default=0)
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("task", "sku", "bin")

    @property
    def remaining(self):
        return max(0, self.qty - self.picked_qty)


class PackingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    picking_task = models.OneToOneField(
        PickingTask, on_delete=models.CASCADE, related_name="packing_task"
    )
    packer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="packing_tasks",
    )
    status = models.CharField(max_length=30, choices=PACK_STATUS_CHOICES, default="pending", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    total_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True, default="")

    def __str__(self):
        return f"PackTask {self.picking_task.order_id} ({self.status})"


class PackingItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    packing_task = models.ForeignKey(PackingTask, related_name="items", on_delete=models.CASCADE)
    sku = models.ForeignKey("inventory.SKU", on_delete=models.CASCADE)
    qty = models.IntegerField()
    packed_qty = models.IntegerField(default=0)

    class Meta:
        unique_together = ("packing_task", "sku")


class DispatchRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=128, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="dispatches")
    packing_task = models.OneToOneField(
        PackingTask, on_delete=models.CASCADE, related_name="dispatch_record"
    )
    status = models.CharField(max_length=30, choices=DISPATCH_STATUS_CHOICES, default="ready", db_index=True)
    rider_id = models.CharField(max_length=128, blank=True, null=True)  # can link to delivery app
    pickup_otp = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Dispatch {self.order_id} ({self.status})"


# --------- Skip / Short pick / Fulfilment cancel --------- #

class PickSkip(models.Model):
    """
    Picker could not find SKU in the bin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField("PickItem", on_delete=models.CASCADE, related_name="skip")
    picker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pick_skips",
    )
    reason = models.CharField(max_length=255, blank=True)
    skipped_at = models.DateTimeField(auto_now_add=True)
    reopened = models.BooleanField(default=False)


class ShortPickIncident(models.Model):
    """
    Picked less than required qty even after trying.
    """
    STATUS_CHOICES = [
        ("open", "open"),
        ("resolved", "resolved"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField(
        "PickItem", on_delete=models.CASCADE, related_name="short_pick_incident"
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="short_picks_reported",
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="open")
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="short_picks_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")


class FulfillmentCancel(models.Model):
    """
    Admin action: mark an item as fulfilment-cancelled (refund will be processed by Payments).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField("PickItem", on_delete=models.CASCADE, related_name="fulfillment_cancel")
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fulfillment_cancels",
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


# --------- Inbound: GRN + Putaway --------- #

class GRN(models.Model):
    """
    Goods Receipt Note for inbound shipment.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn_no = models.CharField(max_length=64, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="grns")
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_grns",
    )
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default="received")  # received, putaway_in_progress, completed

    def __str__(self):
        return f"GRN {self.grn_no} ({self.warehouse.code})"


class PutawayTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name="putaway_tasks")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="putaway_tasks")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="putaway_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        default="pending",
        choices=[("pending", "pending"), ("in_progress", "in_progress"), ("completed", "completed")],
    )

    def __str__(self):
        return f"PutawayTask {self.grn.grn_no}"


class PutawayItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(PutawayTask, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey("inventory.SKU", on_delete=models.CASCADE)
    expected_qty = models.IntegerField()
    bin = models.ForeignKey("Bin", null=True, blank=True, on_delete=models.SET_NULL)
    placed_qty = models.IntegerField(default=0)
    placed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("task", "sku")


# --------- Cycle count / Stock audit --------- #

class CycleCountTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="cycle_tasks")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cycle_tasks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default="")


class CycleCountItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    cycle_task = models.ForeignKey(CycleCountTask, on_delete=models.CASCADE, related_name="items")
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    sku = models.ForeignKey("inventory.SKU", on_delete=models.CASCADE)
    expected_qty = models.IntegerField(default=0)
    counted_qty = models.IntegerField(null=True, blank=True)
    counted_at = models.DateTimeField(null=True, blank=True)
    adjusted = models.BooleanField(default=False)
    adjusted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cycle_adjustments",
    )
    adjusted_at = models.DateTimeField(null=True, blank=True)
    adjustment_note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = ("cycle_task", "bin", "sku")


# --------- Idempotency for WMS write APIs --------- #

class IdempotencyKey(models.Model):
    key = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    route = models.CharField(max_length=255, blank=True, null=True)
    request_hash = models.CharField(max_length=128, blank=True, null=True)
    response_status = models.IntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at