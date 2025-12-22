from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RiderProfileViewSet, RiderEarningsViewSet

router = DefaultRouter()
router.register(r'profile', RiderProfileViewSet, basename='rider-profile')
router.register(r'earnings', RiderEarningsViewSet, basename='rider-earnings')

urlpatterns = [
    path('', include(router.urls)),
]