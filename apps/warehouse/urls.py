from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    # ViewSets
    WarehouseViewSet,
    BinViewSet,
    PickingTaskViewSet,
    PackingTaskViewSet,
    DispatchViewSet,

    # Listings
    BinInventoryList,
    InventoryStockList,

    # Automation
    OrderWebhookAPIView,

    # Picking
    scan_pick_view,
    pick_skip_view,
    short_pick_view,
    admin_fc_view,

    # Packing
    create_packing_view,
    complete_packing_view,

    # Inbound (GRN + Putaway)
    create_grn_putaway_view,
    place_putaway_item_view,

    # Cycle count
    create_cycle_view,
    record_cycle_item_view,
)

# ===============================================================
#                     ROUTER (ViewSets)
# ===============================================================

router = DefaultRouter()
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"bins", BinViewSet, basename="bin")
router.register(r"picking/tasks", PickingTaskViewSet, basename="picking-task")
router.register(r"packing/tasks", PackingTaskViewSet, basename="packing-task")
router.register(r"dispatch", DispatchViewSet, basename="dispatch")

urlpatterns = [

    # ===============================================================
    #                          STRUCTURE APIs
    # ===============================================================
    path("", include(router.urls)),

    # ===============================================================
    #                          INVENTORY
    # ===============================================================
    path("inventory/bin/", BinInventoryList.as_view(), name="wms-bin-inventory"),
    path("inventory/stock/", InventoryStockList.as_view(), name="wms-inventory-stock"),

    # ===============================================================
    #                          ORDER AUTOMATION
    # ===============================================================
    path("auto/order/process/", OrderWebhookAPIView.as_view(), name="wms-auto-process-order"),

    # ===============================================================
    #                          PICKING (PICKER ONLY)
    # ===============================================================
    path("picking/scan/", scan_pick_view, name="wms-pick-scan"),
    path("picking/skip/", pick_skip_view, name="wms-pick-skip"),
    path("picking/short/", short_pick_view, name="wms-pick-short"),
    path("picking/fulfillment-cancel/", admin_fc_view, name="wms-pick-fc"),

    # ===============================================================
    #                          PACKING (PACKER ONLY)
    # ===============================================================
    path("packing/create/", create_packing_view, name="wms-pack-create"),
    path("packing/complete/", complete_packing_view, name="wms-pack-complete"),

    # ===============================================================
    #                     INBOUND (GRN + PUTAWAY – MANAGER ONLY)
    # ===============================================================
    path("inbound/grn/create/", create_grn_putaway_view, name="wms-grn-create"),
    path("inbound/putaway/place/", place_putaway_item_view, name="wms-putaway-place"),

    # ===============================================================
    #                       CYCLE COUNT (AUDITOR ONLY)
    # ===============================================================
    path("audit/cycle/create/", create_cycle_view, name="wms-cycle-create"),
    path("audit/cycle/record/", record_cycle_item_view, name="wms-cycle-record"),
]
