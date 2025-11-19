import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

# =========================================================
# 1. PHYSICAL STRUCTURE
# =========================================================

class Warehouse(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Zone(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="zones")
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=10)

    def __str__(self): return f"{self.warehouse.code}-{self.code}"

class Bin(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="bins")
    bin_code = models.CharField(max_length=20, unique=True)
    capacity = models.FloatField(default=100.0)
    
    def __str__(self): return self.bin_code

class BinInventory(models.Model):
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name="inventory")
    sku = models.ForeignKey('catalog.SKU', on_delete=models.CASCADE)
    qty = models.PositiveIntegerField(default=0)
    reserved_qty = models.PositiveIntegerField(default=0)

    class Meta: unique_together = ('bin', 'sku')
    
    @property
    def available_qty(self): return self.qty - self.reserved_qty

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('INWARD', 'Inward (GRN)'),
        ('OUTWARD', 'Outward (Dispatch)'),
        ('ADJUSTMENT', 'Adjustment (Lost/Found)'),
        ('RESERVE', 'Order Reservation'),
        ('PUTAWAY', 'Putaway'),
    ]
    sku = models.ForeignKey('catalog.SKU', on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, null=True)
    qty_change = models.IntegerField()
    movement_type = models.CharField(max_length=32, choices=MOVEMENT_TYPES)
    reference_id = models.CharField(max_length=100, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

# =========================================================
# TASKS
# =========================================================

class PickingTask(models.Model):
    TASK_STATUS = [('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed')]
    order_id = models.CharField(max_length=50)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='picking_tasks')
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PickItem(models.Model):
    task = models.ForeignKey(PickingTask, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey('catalog.SKU', on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    qty_to_pick = models.PositiveIntegerField()
    picked_qty = models.PositiveIntegerField(default=0)

class PackingTask(models.Model):
    picking_task = models.OneToOneField(PickingTask, on_delete=models.CASCADE, related_name="packing_task")
    packer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="packing_tasks")
    status = models.CharField(max_length=30, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

class DispatchRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    packing_task = models.OneToOneField(PackingTask, on_delete=models.CASCADE, related_name="dispatch_record")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=128, db_index=True)
    pickup_otp = models.CharField(max_length=10, blank=True, null=True)
    status = models.CharField(max_length=30, default="ready")
    created_at = models.DateTimeField(auto_now_add=True)

# Others (GRN, Putaway, CycleCount) removed for brevity but should be clean like above.

# =========================================================
# 4. PICKING ERROR RESOLUTION & CANCELLATION
# =========================================================

class PickSkip(models.Model):
    """
    Picker dwara item skip karne ka record.
    """
    task = models.ForeignKey(PickingTask, on_delete=models.CASCADE, related_name="skips")
    pick_item = models.ForeignKey(PickItem, on_delete=models.CASCADE, related_name="skips")
    skipped_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255) # 'Not found', 'Damaged', etc.
    is_resolved = models.BooleanField(default=False)
    reopen_after_scan = models.BooleanField(default=False) # Skip ke baad dobara dikhana hai kya?
    created_at = models.DateTimeField(auto_now_add=True)

class ShortPickIncident(models.Model):
    """
    Jab PickSkip ko inventory check ke baad 'Short Pick' declare kiya jata hai.
    """
    skip = models.OneToOneField(PickSkip, on_delete=models.CASCADE)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    short_picked_qty = models.IntegerField() # Kitna stock kam tha
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class FulfillmentCancel(models.Model):
    """
    Jab koi item order se permanently cancel hota hai (refund ke liye).
    """
    pick_item = models.ForeignKey(PickItem, on_delete=models.CASCADE, related_name="fc_records")
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=255)
    refund_initiated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



GRN_STATUS_CHOICES = [("pending", "Pending"), ("received", "Received"), ("putaway_complete", "Putaway Complete")]

class GRN(models.Model):
    """Goods Receipt Note (GRN)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="grns")
    grn_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=30, choices=GRN_STATUS_CHOICES, default="pending")
    received_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

class GRNItem(models.Model):
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name="items")
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    expected_qty = models.IntegerField()
    received_qty = models.IntegerField(default=0)
    
class PutawayTask(models.Model):
    grn = models.OneToOneField(GRN, on_delete=models.CASCADE, related_name="putaway_task")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    putaway_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="putaway_tasks")
    status = models.CharField(max_length=30, default="pending") # 'pending', 'in_progress', 'completed'
    created_at = models.DateTimeField(auto_now_add=True)

class PutawayItem(models.Model):
    task = models.ForeignKey(PutawayTask, on_delete=models.CASCADE, related_name="items")
    grn_item = models.ForeignKey(GRNItem, on_delete=models.CASCADE)
    placed_qty = models.IntegerField(default=0)
    
    # Kahan rakha gaya hai
    placed_bin = models.ForeignKey(Bin, on_delete=models.SET_NULL, null=True, blank=True)


# --- Cycle Count ---

CC_STATUS_CHOICES = [("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed")]

class CycleCountTask(models.Model):
    """
    Inventory accuracy check ke liye.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="cc_tasks")
    task_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="cc_tasks")
    status = models.CharField(max_length=30, choices=CC_STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

class CycleCountItem(models.Model):
    task = models.ForeignKey(CycleCountTask, on_delete=models.CASCADE, related_name="items")
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    expected_qty = models.IntegerField() # DB se uthaya gaya qty
    counted_qty = models.IntegerField(null=True, blank=True)
    adjusted = models.BooleanField(default=False)




class IdempotencyKey(models.Model):
    """
    Middleware dwara istemaal kiya jata hai taaki ek hi request do baar process na ho.
    Jaisa ki system design mein bataya gaya hai, yeh external integrations ke liye hai.
    """
    key = models.CharField(max_length=255, unique=True, db_index=True)
    route = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64, blank=True)
    response_status = models.SmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.key
    
    def is_expired(self):
        return self.expires_at < timezone.now()

    class Meta:
        verbose_name_plural = "Idempotency Keys"