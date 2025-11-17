# apps/warehouse/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    WarehouseViewSet,
    BinViewSet,
    PickingTaskViewSet,
    PackingTaskViewSet,
    DispatchViewSet,
    BinInventoryList,
    InventoryStockList,
    OrderWebhookAPIView,
    scan_pick_view,
    pick_skip_view,
    short_pick_view,
    admin_fc_view,
    create_packing_view,
    complete_packing_view,
    create_grn_putaway_view,
    place_putaway_item_view,
    create_cycle_view,
    record_cycle_item_view,
)

router = DefaultRouter()
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"bins", BinViewSet, basename="bin")
router.register(r"pick-tasks", PickingTaskViewSet, basename="picktask")
router.register(r"pack-tasks", PackingTaskViewSet, basename="packtask")
router.register(r"dispatch", DispatchViewSet, basename="dispatch")

urlpatterns = [
    # ViewSets
    path("", include(router.urls)),

    # Inventory listings
    path("bin-inventory/", BinInventoryList.as_view(), name="bin-inventory"),
    path("inventory-stock/", InventoryStockList.as_view(), name="inventory-stock"),

    # Order automation
    path("auto/process_order/", OrderWebhookAPIView.as_view(), name="auto-process-order"),

    # Picking
    path("pick/scan/", scan_pick_view, name="pick-scan"),
    path("pick/skip/", pick_skip_view, name="pick-skip"),
    path("pick/short/", short_pick_view, name="pick-short"),
    path("pick/fulfillment_cancel/", admin_fc_view, name="pick-fc"),

    # Packing
    path("pack/create/", create_packing_view, name="pack-create"),
    path("pack/complete/", complete_packing_view, name="pack-complete"),

    # Putaway / GRN
    path("putaway/create_grn/", create_grn_putaway_view, name="create-grn"),
    path("putaway/place/", place_putaway_item_view, name="putaway-place"),

    # Cycle count
    path("cycle/create/", create_cycle_view, name="cycle-create"),
    path("cycle/record/", record_cycle_item_view, name="cycle-record"),
]
