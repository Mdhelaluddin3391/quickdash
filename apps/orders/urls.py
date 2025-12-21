# apps/orders/urls.py
from rest_framework import routers
from django.urls import path
from .views import CheckoutView, OrderViewSet, CartView, AddToCartView, PaymentVerificationView
from django.urls import path
from .views import CreateOrderAPIView

router = routers.DefaultRouter()
router.register(r'', OrderViewSet, basename='orders')

# FIX: Specific paths must come BEFORE router.urls
# Otherwise, the router interprets 'cart' as an order_id (e.g. /orders/cart/ -> get order with id='cart')
urlpatterns = [
    # Checkout & payment
    path('create/', CheckoutView.as_view(), name='create-order'),
    path('payment/verify/', PaymentVerificationView.as_view(), name='payment-verify'),

    # Cart endpoints
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/add/', AddToCartView.as_view(), name='cart-add'),
    path('api/v1/orders/create/', CreateOrderAPIView.as_view(), name='create-order'),
] + router.urls