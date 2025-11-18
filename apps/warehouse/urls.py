# apps/warehouse/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WarehouseViewSet, 
    PickingTaskViewSet, 
    BinInventoryList, 
    scan_pick_view, 
    complete_packing_view,
    # New Imports
    CreateGRNAPIView,
    place_putaway_item_view,
    mark_pickitem_skipped_view,
    AdminResolveShortPickAPIView,
    AdminFulfillmentCancelAPIView,
    CycleCountTaskViewSet,
    record_cycle_count_view
)

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet)
router.register(r'picking/tasks', PickingTaskViewSet)
router.register(r'cycle-count/tasks', CycleCountTaskViewSet) # New ViewSet

urlpatterns = [
    path('', include(router.urls)),
    
    # Inventory & Bin Check (Manager)
    # GET /api/v1/wms/inventory/bin/
    path('inventory/bin/', BinInventoryList.as_view(), name='wms-bin-inventory-list'),
    
    # Picking Workflow (Picker/Packer)
    # POST /api/v1/wms/picking/scan/
    path('picking/scan/', scan_pick_view, name='wms-picking-scan'),
    # POST /api/v1/wms/picking/skip/
    path('picking/skip/', mark_pickitem_skipped_view, name='wms-picking-skip'),
    # POST /api/v1/wms/packing/complete/
    path('packing/complete/', complete_packing_view, name='wms-packing-complete'),

    # Picking Resolution (Manager/Admin)
    # POST /api/v1/wms/resolution/shortpick/
    path('resolution/shortpick/', AdminResolveShortPickAPIView.as_view(), name='wms-resolve-shortpick'),
    # POST /api/v1/wms/resolution/fc/
    path('resolution/fc/', AdminFulfillmentCancelAPIView.as_view(), name='wms-admin-fc'),
    
    # Inbound / Putaway (Manager/Picker)
    # POST /api/v1/wms/inbound/grn/
    path('inbound/grn/', CreateGRNAPIView.as_view(), name='wms-create-grn'),
    # POST /api/v1/wms/inbound/putaway/place/
    path('inbound/putaway/place/', place_putaway_item_view, name='wms-putaway-place'),
    
    # Cycle Count (Manager/Auditor)
    # POST /api/v1/wms/cycle-count/record/
    path('cycle-count/record/', record_cycle_count_view, name='wms-cc-record'),
]