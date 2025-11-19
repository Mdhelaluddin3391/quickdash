import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.catalog.models import SKU



PICK_STATUS_CHOICES = [("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed")]
# =========================================================
# 1. PHYSICAL STRUCTURE
# =========================================================

class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True) # e.g., 'DEL-01'
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Zone(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="zones")
    code = models.CharField(max_length=50) # e.g., 'AMBIENT', 'COLD'
    name = models.CharField(max_length=150, blank=True)

    class Meta: unique_together = ("warehouse", "code")
    def __str__(self): return f"{self.warehouse.code}/{self.code}"

class Aisle(models.Model):
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="aisles")
    code = models.CharField(max_length=50) # e.g., 'A1'
    class Meta: unique_together = ("zone", "code")
    def __str__(self): return f"{self.zone}/{self.code}"

class Shelf(models.Model):
    aisle = models.ForeignKey(Aisle, on_delete=models.CASCADE, related_name="shelves")
    code = models.CharField(max_length=50) # e.g., 'S1'
    class Meta: unique_together = ("aisle", "code")
    def __str__(self): return f"{self.aisle}/{self.code}"

class Bin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="bins")
    code = models.CharField(max_length=50) # e.g., 'B01'
    bin_type = models.CharField(max_length=20, default="default")
    is_active = models.BooleanField(default=True)

    class Meta: unique_together = ("shelf", "code")
    def __str__(self): return f"{self.shelf}/{self.code}"

# =========================================================
# 2. PHYSICAL INVENTORY (BIN LEVEL)
# =========================================================

class BinInventory(models.Model):
    """
    Asli physical stock jo bins mein rakha hai.
    """
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE, related_name='inventory')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, related_name='bin_inventories')
    qty = models.IntegerField(default=0)
    reserved_qty = models.IntegerField(default=0) # Picking ke liye reserved
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('bin', 'sku')

    def __str__(self):
        return f"{self.bin.code} | {self.sku.sku_code}: {self.qty}"

class StockMovement(models.Model):
    """
    Audit Trail: Har stock movement ka record (Inbound/Outbound).
    """
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, null=True, on_delete=models.SET_NULL)
    change_type = models.CharField(max_length=50) # 'reserve', 'pick', 'putaway', 'adjustment'
    delta_qty = models.IntegerField()
    reference_id = models.CharField(max_length=128, null=True, blank=True) # Order ID ya GRN ID
    created_at = models.DateTimeField(auto_now_add=True)

# =========================================================
# 3. PICKING & PACKING TASKS
# =========================================================

PICK_STATUS_CHOICES = [("pending", "Pending"), ("in_progress", "In Progress"), ("completed", "Completed")]

class PickingTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.CharField(max_length=128, db_index=True)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="picking_tasks")
    picker = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="picking_tasks")
    status = models.CharField(max_length=30, choices=PICK_STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

class PickItem(models.Model):
    task = models.ForeignKey(PickingTask, related_name="items", on_delete=models.CASCADE)
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE)
    bin = models.ForeignKey(Bin, on_delete=models.CASCADE)
    qty = models.IntegerField() # Kitna uthana hai
    picked_qty = models.IntegerField(default=0) # Kitna utha liya

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
    rider_id = models.CharField(max_length=128, blank=True, null=True)
    pickup_otp = models.CharField(max_length=10, blank=True, null=True)
    status = models.CharField(max_length=30, default="ready") # 'ready', 'assigned', 'picked_up'
    created_at = models.DateTimeField(auto_now_add=True)




# apps/warehouse/models.py
# ... (Existing imports)
# ... (Existing Models 1, 2, 3 - DispatchRecord tak)

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