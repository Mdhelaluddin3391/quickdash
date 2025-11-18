from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WarehouseViewSet, PickingTaskViewSet, BinInventoryList, scan_pick_view, complete_packing_view

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet)
router.register(r'picking/tasks', PickingTaskViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('inventory/bin/', BinInventoryList.as_view()),
    path('picking/scan/', scan_pick_view),
    path('packing/complete/', complete_packing_view),
]