import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


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
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='zones')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = ('warehouse', 'code')

    def __str__(self):
        return f"{self.warehouse.code}/{self.code}"


class Aisle(models.Model):
    id = models.AutoField(primary_key=True)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='aisles')
    code = models.CharField(max_length=50)

    class Meta:
        unique_together = ('zone', 'code')

    def __str__(self):
        return f"{self.zone}/{self.code}"


class Shelf(models.Model):
    id = models.AutoField(primary_key=True)
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name='shelves')
    code = models.CharField(max_length=50)

    class Meta:
        unique_together = ('aisle', 'code')

    def __str__(self):
        return f"{self.aisle}/{self.code}"


class Bin(models.Model):
    id = models.AutoField(primary_key=True)
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name='bins')
    code = models.CharField(max_length=50)  # ex: "A1-B2-03"
    preferred_sku = models.ForeignKey('inventory.SKU', null=True, blank=True, on_delete=models.SET_NULL)
    capacity = models.IntegerField(default=100)
    metadata = models.JSONField(default=dict, blank=True)  # e.g., {"temperature":"cold"}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('shelf', 'code')

    def __str__(self):
        return f"{self.shelf}/{self.code}"




PICK_STATUS_CHOICES = [
    ('pending','pending'),
    ('assigned','assigned'),
    ('in_progress','in_progress'),
    ('partial','partial'),
    ('completed','completed'),
    ('cancelled','cancelled'),
]

PACK_STATUS_CHOICES = [
    ('pending','pending'),
    ('in_progress','in_progress'),
    ('packed','packed'),
    ('cancelled','cancelled'),
]

DISPATCH_STATUS_CHOICES = [
    ('ready','ready'),
    ('assigned','assigned'),
    ('picked_up','picked_up'),
    ('delivered','delivered'),
    ('failed','failed'),
]

class PickingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=128, db_index=True)  # external order id
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='picking_tasks')
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, choices=PICK_STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

    def __str__(self):
        return f"PickTask {self.order_id} ({self.status})"

class PickItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    task = models.ForeignKey(PickingTask, related_name='items', on_delete=models.CASCADE)
    sku = models.ForeignKey('inventory.SKU', on_delete=models.CASCADE)
    bin = models.ForeignKey('Bin', on_delete=models.CASCADE)
    qty = models.IntegerField()
    picked_qty = models.IntegerField(default=0)
    scanned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('task','sku','bin')

    def remaining(self):
        return max(0, self.qty - self.picked_qty)

class PackingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    picking_task = models.OneToOneField(PickingTask, on_delete=models.CASCADE, related_name='packing_task')
    packer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, choices=PACK_STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    packed_at = models.DateTimeField(null=True, blank=True)
    package_label = models.CharField(max_length=255, blank=True, default='')  # generated label/barcode

    def __str__(self):
        return f"Packing {self.picking_task.order_id} ({self.status})"

class PackingItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    packing_task = models.ForeignKey(PackingTask, related_name='items', on_delete=models.CASCADE)
    sku = models.ForeignKey('inventory.SKU', on_delete=models.CASCADE)
    qty = models.IntegerField()

class DispatchRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=128, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='dispatches')
    packing_task = models.ForeignKey(PackingTask, null=True, blank=True, on_delete=models.SET_NULL)
    courier = models.CharField(max_length=150, blank=True)  # external carrier name or rider id
    courier_id = models.CharField(max_length=128, blank=True) # link to rider system
    status = models.CharField(max_length=30, choices=DISPATCH_STATUS_CHOICES, default='ready', db_index=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Dispatch {self.order_id} ({self.status})"


# ---------- append to apps/warehouse/models.py ----------

class PickSkip(models.Model):
    """
    When picker cannot find SKU at pick time and chooses 'skip for now'.
    Later WMS will surface skipped items to picker again.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField('PickItem', on_delete=models.CASCADE, related_name='skip')
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255, blank=True)
    skipped_at = models.DateTimeField(auto_now_add=True)
    reopen_after_scan = models.BooleanField(default=False)  # kept for logic if we auto-reopen
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='skip_resolved_by', on_delete=models.SET_NULL)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True, default='')

    def mark_resolved(self, user=None, note=''):
        self.resolved = True
        self.resolved_by = user
        self.resolution_note = note
        self.resolved_at = timezone.now()
        self.save(update_fields=['resolved','resolved_by','resolved_at','resolution_note'])


class ShortPickIncident(models.Model):
    """
    If picker marks item as 'not found' after retries or QA marks it missing,
    create an incident for admin to resolve (cancel fulfillment, refund, raise PO, etc).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField('PickItem', on_delete=models.CASCADE, related_name='short_pick_incident')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, default='open')  # open, escalated, resolved, cancelled
    note = models.TextField(blank=True, default='')

    def escalate(self, note=''):
        self.status = 'escalated'
        self.note = note
        self.save(update_fields=['status','note'])

    def resolve(self, note=''):
        self.status = 'resolved'
        self.note = note
        self.save(update_fields=['status','note'])


class FulfillmentCancel(models.Model):
    """
    Admin action: mark an order-line or pick_item as fulfillment-cancelled (FC).
    Payments/refund handled by payments system separately.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pick_item = models.OneToOneField('PickItem', on_delete=models.CASCADE, related_name='fulfillment_cancel')
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)





# ---------- append to apps/warehouse/models.py ----------
class GRN(models.Model):
    """
    Goods Receipt Note for inbound shipment.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn_no = models.CharField(max_length=64, unique=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='grns')
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, default='received')  # received, putaway_in_progress, completed

class PutawayTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name='putaway_tasks')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='putaway_tasks')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, default='pending')  # pending, in_progress, completed, cancelled
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PutawayItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    putaway_task = models.ForeignKey(PutawayTask, related_name='items', on_delete=models.CASCADE)
    sku = models.ForeignKey('inventory.SKU', on_delete=models.CASCADE)
    qty = models.IntegerField()
    suggested_bin = models.ForeignKey('Bin', null=True, blank=True, on_delete=models.SET_NULL)
    placed_bin = models.ForeignKey('Bin', null=True, blank=True, related_name='putaway_items', on_delete=models.SET_NULL)
    placed_qty = models.IntegerField(default=0)



class CycleCountTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='cycle_counts')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=30, default='pending')  # pending, in_progress, completed
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

class CycleCountItem(models.Model):
    id = models.BigAutoField(primary_key=True)
    cycle_task = models.ForeignKey(CycleCountTask, related_name='items', on_delete=models.CASCADE)
    bin = models.ForeignKey('Bin', on_delete=models.CASCADE)
    sku = models.ForeignKey('inventory.SKU', on_delete=models.CASCADE)
    expected_qty = models.IntegerField()
    counted_qty = models.IntegerField(null=True, blank=True)
    counted_at = models.DateTimeField(null=True, blank=True)
    adjusted = models.BooleanField(default=False)
    adjusted_at = models.DateTimeField(null=True, blank=True)
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='adjusted_counts', on_delete=models.SET_NULL)
    adjustment_note = models.TextField(blank=True, default='')

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