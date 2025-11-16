# apps/warehouse/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# ViewSets
from .views import (
    WarehouseViewSet,
    BinViewSet,
    PickingTaskViewSet,
    PackingTaskViewSet,
    DispatchViewSet,
)

# API endpoints
from .views import (
    BinInventoryList,
    ReserveStockAPIView,
    PickScanAPIView,
    OrderWebhookAPIView,
    pick_skip_view,
    pick_unscan_view,
    admin_fc_view,
    create_grn_putaway_view,
    place_putaway_item_view,
    create_cycle_view,
    record_cycle_item_view,
)

# -----------------------------------------------------------
# ROUTER (VIEWSETS)
# -----------------------------------------------------------
router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'bins', BinViewSet, basename='bin')
router.register(r'pick-tasks', PickingTaskViewSet, basename='picktask')
router.register(r'pack-tasks', PackingTaskViewSet, basename='packtask')
router.register(r'dispatch', DispatchViewSet, basename='dispatch')


# -----------------------------------------------------------
# URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    path('', include(router.urls)),

    # Inventory & Reservation
    path('bin-inventory/', BinInventoryList.as_view(), name='bin-inventory-list'),
    path('warehouses/<uuid:warehouse_id>/reserve/', ReserveStockAPIView.as_view(), name='warehouse-reserve'),

    # Picking flow
    path('pick/scan/', PickScanAPIView.as_view(), name='pick-scan'),
    path('pick/skip/', pick_skip_view, name='pick-skip'),
    path('pick/unscan/', pick_unscan_view, name='pick-unscan'),
    path('pick/fulfillment_cancel/', admin_fc_view, name='pick-fc'),

    # Automation webhook
    path('auto/process_order/', OrderWebhookAPIView.as_view(), name='auto-process-order'),

    # Putaway inbound flow
    path('putaway/create_grn/', create_grn_putaway_view, name='create-grn'),
    path('putaway/place/', place_putaway_item_view, name='putaway-place'),

    # Cycle count / Audit
    path('cycle/create/', create_cycle_view, name='cycle-create'),
    path('cycle/record/', record_cycle_item_view, name='cycle-record'),
]
