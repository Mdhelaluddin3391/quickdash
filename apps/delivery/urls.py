from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryJobViewSet

router = DefaultRouter()
router.register(r'jobs', DeliveryJobViewSet, basename='delivery-jobs')

urlpatterns = [
    path('', include(router.urls)),
]