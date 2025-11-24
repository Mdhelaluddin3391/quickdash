# apps/delivery/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryTaskViewSet,
    RiderDashboardView,
    RiderEarningsView,
)

router = DefaultRouter()
router.register(
    r"tasks",
    DeliveryTaskViewSet,
    basename="delivery-tasks",
)

urlpatterns = [
    path("dashboard/", RiderDashboardView.as_view(), name="rider-dashboard"),
    path("earnings/", RiderEarningsView.as_view(), name="rider-earnings"),
    path("", include(router.urls)),
]
