from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, AddressViewSet

router = DefaultRouter()
# Explicit 'addresses' route
router.register(r'addresses', AddressViewSet, basename='customer-addresses')

urlpatterns = [
    # Custom profile endpoint
    path('profile/', CustomerViewSet.as_view({'get': 'profile'}), name='customer-profile'),
    path('', include(router.urls)),
]