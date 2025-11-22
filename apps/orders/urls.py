# apps/orders/urls.py
from rest_framework import routers
from django.urls import path
from .views import CheckoutView, OrderViewSet, CartView, AddToCartView, PaymentVerificationView,CancelOrderView

router = routers.DefaultRouter()
router.register(r'', OrderViewSet, basename='orders')

urlpatterns = router.urls + [
    # Checkout & payment
    path('create/', CheckoutView.as_view(), name='create-order'),
    path('payment/verify/', PaymentVerificationView.as_view(), name='payment-verify'),

    # Cart endpoints
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/add/', AddToCartView.as_view(), name='cart-add'),

    # NEW: cancel order
    path('<uuid:pk>/cancel/', CancelOrderView.as_view(), name='order-cancel'),
    path('<uuid:pk>/cancel/', CancelOrderView.as_view(), name='order-cancel'),

]