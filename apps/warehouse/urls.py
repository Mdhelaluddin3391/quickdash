# apps/warehouse/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from . import views  # updated views


class _NotImplementedAPIView(APIView):
    def dispatch(self, request, *args, **kwargs):
        return Response({"detail": "Not Implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)


def _resolve(name):
    return getattr(views, name, None)


router = DefaultRouter()

WarehouseViewSet = _resolve("WarehouseViewSet")
PickingTaskViewSet = _resolve("PickingTaskViewSet") or _resolve("PickerTaskViewSet")
CycleCountTaskViewSet = _resolve("CycleCountTaskViewSet")

if WarehouseViewSet is not None:
    if getattr(WarehouseViewSet, "queryset", None) is not None:
        router.register(r"warehouses", WarehouseViewSet)
    else:
        router.register(r"warehouses", WarehouseViewSet, basename="warehouses")

if PickingTaskViewSet is not None:
    if getattr(PickingTaskViewSet, "queryset", None) is not None:
        router.register(r"picking/tasks", PickingTaskViewSet)
    else:
        router.register(r"picking/tasks", PickingTaskViewSet, basename="picking-tasks")

if CycleCountTaskViewSet is not None:
    if getattr(CycleCountTaskViewSet, "queryset", None) is not None:
        router.register(r"cycle-count/tasks", CycleCountTaskViewSet)
    else:
        router.register(r"cycle-count/tasks", CycleCountTaskViewSet, basename="cycle-count-tasks")

urlpatterns = [
    path("", include(router.urls)),

    path(
        "inventory/bin/",
        (_resolve("BinInventoryList") or _NotImplementedAPIView).as_view(),
        name="wms-bin-inventory-list",
    ),

    path(
        "picking/scan/",
        _resolve("scan_pick_view") or _NotImplementedAPIView.as_view(),
        name="wms-picking-scan",
    ),
    path(
        "picking/skip/",
        _resolve("mark_pickitem_skipped_view") or _NotImplementedAPIView.as_view(),
        name="wms-picking-skip",
    ),
    path(
        "packing/complete/",
        _resolve("complete_packing_view") or _NotImplementedAPIView.as_view(),
        name="wms-packing-complete",
    ),

    path(
        "dispatch/verify-otp/",
        _resolve("dispatch_otp_verify_view") or _NotImplementedAPIView.as_view(),
        name="wms-dispatch-otp-verify",
    ),

    path(
        "resolution/shortpick/",
        (_resolve("AdminResolveShortPickAPIView") or _NotImplementedAPIView).as_view(),
        name="wms-resolve-shortpick",
    ),
    path(
        "resolution/fc/",
        (_resolve("AdminFulfillmentCancelAPIView") or _NotImplementedAPIView).as_view(),
        name="wms-admin-fc",
    ),

    path(
        "inbound/grn/",
        (_resolve("CreateGRNAPIView") or _NotImplementedAPIView).as_view(),
        name="wms-create-grn",
    ),
    path(
        "inbound/putaway/place/",
        _resolve("place_putaway_item_view") or _NotImplementedAPIView.as_view(),
        name="wms-putaway-place",
    ),

    path(
        "cycle-count/create/",
        (_resolve("CreateCycleCountView") or _NotImplementedAPIView).as_view(),
        name="wms-cc-create",
    ),
    path(
        "cycle-count/record/",
        _resolve("record_cycle_count_view") or _NotImplementedAPIView.as_view(),
        name="wms-cc-record",
    ),
]
