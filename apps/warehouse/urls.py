from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"warehouses", views.WarehouseViewSet, basename="warehouses")
router.register(r"bins", views.BinViewSet, basename="warehouse-bins")

# Task Management Routers
router.register(r"picking/tasks", views.PickingTaskViewSet, basename="picking-tasks")
router.register(r"packing/tasks", views.PackingTaskViewSet, basename="packing-tasks")
router.register(r"putaway/tasks", views.PutawayTaskViewSet, basename="putaway-tasks")
router.register(r"inbound/grn-list", views.GRNViewSet, basename="grn-list")
router.register(r"cycle-count/tasks", views.CycleCountTaskViewSet, basename="cycle-count-tasks")

urlpatterns = [
    path("", include(router.urls)),

    path("inventory/bin/", views.BinInventoryList.as_view(), name="wms-bin-inventory-list"),

    # Picking / Packing Actions
    path("picking/scan/", views.scan_pick_view, name="wms-picking-scan"),
    path("picking/skip/", views.mark_pickitem_skipped_view, name="wms-picking-skip"),
    path("packing/complete/", views.complete_packing_view, name="wms-packing-complete"),

    # Dispatch
    path("dispatch/verify-otp/", views.dispatch_otp_verify_view, name="wms-dispatch-otp-verify"),

    # Exceptions
    path("resolution/shortpick/", views.AdminResolveShortPickAPIView.as_view(), name="wms-resolve-shortpick"),
    path("resolution/fc/", views.AdminFulfillmentCancelAPIView.as_view(), name="wms-admin-fc"),

    # Inbound Actions
    path("inbound/grn/", views.CreateGRNAPIView.as_view(), name="wms-create-grn"),
    path("inbound/putaway/place/", views.place_putaway_item_view, name="wms-putaway-place"),

    # Cycle Count Actions
    path("cycle-count/create/", views.CreateCycleCountView.as_view(), name="wms-cc-create"),
    path("cycle-count/record/", views.record_cycle_count_view, name="wms-cc-record"),

    # Location Services
    path("location/check-service/", views.CheckServiceabilityAPIView.as_view(), name="wms-check-service-availability"),
    path("location/nearest-service/", views.GetNearestServiceAreaAPIView.as_view(), name="wms-nearest-service-area"),
    path("location/service-areas/", views.ServiceAreaListAPIView.as_view(), name="wms-service-areas-list"),
]