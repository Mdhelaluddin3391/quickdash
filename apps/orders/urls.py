# apps/orders/urls.py
from django.urls import path
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

# Import views module and resolve names dynamically to prevent import-time failures
from . import views


class _NotImplementedAPIView(APIView):
    def dispatch(self, request, *args, **kwargs):
        return Response({"detail": "Not Implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED)


def _resolve(name):
    return getattr(views, name, None)

urlpatterns = [
    # Naya order create karne ke liye
    # POST /api/v1/orders/create/
    path('create/', (_resolve('CreateOrderAPIView') or _resolve('CheckoutView') or _NotImplementedAPIView).as_view(), name='create-order'),
    
    # Customer ke saare orders ki list
    # GET /api/v1/orders/
    path('', (_resolve('OrderHistoryAPIView') or _NotImplementedAPIView).as_view(), name='order-history'),
    
    # Ek order ki poori detail
    # GET /api/v1/orders/<uuid:id>/
    path('<uuid:id>/', (_resolve('OrderDetailAPIView') or _NotImplementedAPIView).as_view(), name='order-detail'),

    path('<uuid:id>/cancel/', (_resolve('CancelOrderAPIView') or _NotImplementedAPIView).as_view(), name='cancel-order'),

    path('cart/', (_resolve('ManageCartAPIView') or _NotImplementedAPIView).as_view(), name='manage-cart'),
]