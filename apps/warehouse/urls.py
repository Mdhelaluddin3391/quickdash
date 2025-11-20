# apps/warehouse/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

# Import the views module and reference attributes dynamically. This
# prevents import-time failures when some view classes/functions are
# missing during incremental refactors.
from . import views

# A lightweight fallback view used when an actual view isn't implemented
class _NotImplementedAPIView(APIView):
    def dispatch(self, request, *args, **kwargs):
        return Response({"detail": "Not Implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)

# Helper to resolve a view or return a fallback
def _resolve(name):
    return getattr(views, name, None)

router = DefaultRouter()

# Register viewsets only if they exist to avoid import errors
WarehouseViewSet = _resolve('WarehouseViewSet')
PickingTaskViewSet = _resolve('PickingTaskViewSet') or _resolve('PickerTaskViewSet')
CycleCountTaskViewSet = _resolve('CycleCountTaskViewSet')

if WarehouseViewSet is not None:
    # Only treat viewsets that expose a non-None `queryset` attribute as auto-namable.
    if getattr(WarehouseViewSet, 'queryset', None) is not None:
        router.register(r'warehouses', WarehouseViewSet)
    else:
        router.register(r'warehouses', WarehouseViewSet, basename='warehouses')

if PickingTaskViewSet is not None:
    if getattr(PickingTaskViewSet, 'queryset', None) is not None:
        router.register(r'picking/tasks', PickingTaskViewSet)
    else:
        router.register(r'picking/tasks', PickingTaskViewSet, basename='picking-tasks')

if CycleCountTaskViewSet is not None:
    if getattr(CycleCountTaskViewSet, 'queryset', None) is not None:
        router.register(r'cycle-count/tasks', CycleCountTaskViewSet)
    else:
        router.register(r'cycle-count/tasks', CycleCountTaskViewSet, basename='cycle-count-tasks')

urlpatterns = [
    path('', include(router.urls)),
    
    # Inventory & Bin Check (Manager)
    # GET /api/v1/wms/inventory/bin/
    # Resolve views dynamically; if missing, use a Not Implemented placeholder
    path('inventory/bin/', (_resolve('BinInventoryList') or _NotImplementedAPIView).as_view(), name='wms-bin-inventory-list'),
    
    # Picking Workflow (Picker/Packer)
    # POST /api/v1/wms/picking/scan/
    path('picking/scan/', _resolve('scan_pick_view') or _NotImplementedAPIView.as_view(), name='wms-picking-scan'),
    # POST /api/v1/wms/picking/skip/
    path('picking/skip/', _resolve('mark_pickitem_skipped_view') or _NotImplementedAPIView.as_view(), name='wms-picking-skip'),
    # POST /api/v1/wms/packing/complete/
    path('packing/complete/', _resolve('complete_packing_view') or _NotImplementedAPIView.as_view(), name='wms-packing-complete'),

    # Picking Resolution (Manager/Admin)
    # POST /api/v1/wms/resolution/shortpick/
    path('resolution/shortpick/', (_resolve('AdminResolveShortPickAPIView') or _NotImplementedAPIView).as_view(), name='wms-resolve-shortpick'),
    # POST /api/v1/wms/resolution/fc/
    path('resolution/fc/', (_resolve('AdminFulfillmentCancelAPIView') or _NotImplementedAPIView).as_view(), name='wms-admin-fc'),
    
    # Inbound / Putaway (Manager/Picker)
    # POST /api/v1/wms/inbound/grn/
    path('inbound/grn/', (_resolve('CreateGRNAPIView') or _NotImplementedAPIView).as_view(), name='wms-create-grn'),
    # POST /api/v1/wms/inbound/putaway/place/
    path('inbound/putaway/place/', _resolve('place_putaway_item_view') or _NotImplementedAPIView.as_view(), name='wms-putaway-place'),
    
    # Cycle Count (Manager/Auditor)
    # POST /api/v1/wms/cycle-count/record/
    path('cycle-count/record/', _resolve('record_cycle_count_view') or _NotImplementedAPIView.as_view(), name='wms-cc-record'),
    path('', include(router.urls)),
]