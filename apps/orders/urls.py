# apps/orders/urls.py
from django.urls import path
from .views import (
    CreateOrderAPIView,
    OrderHistoryAPIView,
    OrderDetailAPIView,
    CancelOrderAPIView
)

urlpatterns = [
    # Naya order create karne ke liye
    # POST /api/v1/orders/create/
    path('create/', CreateOrderAPIView.as_view(), name='create-order'),
    
    # Customer ke saare orders ki list
    # GET /api/v1/orders/
    path('', OrderHistoryAPIView.as_view(), name='order-history'),
    
    # Ek order ki poori detail
    # GET /api/v1/orders/<uuid:id>/
    path('<uuid:id>/', OrderDetailAPIView.as_view(), name='order-detail'),

    path('<uuid:id>/cancel/', CancelOrderAPIView.as_view(), name='cancel-order'),
]