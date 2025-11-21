# apps/orders/urls.py
from rest_framework import routers
from .views import CheckoutView
from .views import OrderViewSet

router = routers.DefaultRouter()
router.register(r'', OrderViewSet, basename='orders')

urlpatterns = router.urls + [
    # Keep checkout endpoint separate
    # POST /api/v1/orders/create/
    path('create/', CheckoutView.as_view(), name='create-order'),
]