from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CreateOrderView

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')

urlpatterns = [
    path('checkout/', CreateOrderView.as_view(), name='checkout'),
    path('', include(router.urls)),
]