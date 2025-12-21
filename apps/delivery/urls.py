# apps/delivery/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryTaskViewSet,
    RiderDashboardView,
    RiderEarningsView,
    DeliveryEstimateView 
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
    # This was the line causing the error because the class wasn't imported above
    path("estimate/", DeliveryEstimateView.as_view(), name="delivery-estimate"), 
    path("", include(router.urls)),
]