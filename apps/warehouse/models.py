import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from apps.catalog.models import SKU

# =========================================================
# 1. PHYSICAL STRUCTURE
# =========================================================

class Warehouse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True) # e.g., 'DEL-01'
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