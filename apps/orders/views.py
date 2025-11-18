# apps/orders/views.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsCustomer
from apps.catalog.models import SKU
from .models import Order, OrderItem, OrderTimeline
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    OrderListSerializer
)
from .signals import order_refund_requested
import logging
logger = logging.getLogger(__name__)


class CancelOrderAPIView(APIView):
    """
    Customer khud order cancel kar sake.
    POST /api/v1/orders/<id>/cancel/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, id):
        # Order dhoondhein jo sirf isi customer ka ho
        order = get_object_or_404(Order, id=id, customer=request.user)
        
        # Sirf 'pending' ya 'confirmed' order hi cancel ho sakte hain
        if order.status not in ['pending', 'confirmed']:
            return Response(
                {"detail": "Cannot cancel order at this stage (already processing)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                order.status = 'cancelled'
                order.save(update_fields=['status'])
                
                # Timeline update
                OrderTimeline.objects.create(
                    order=order, 
                    status='cancelled', 
                    notes="Cancelled by customer."
                )
                
                # --- AUTO REFUND LOGIC (Signal) ---
                if order.payment_status == 'paid':
                    # Direct call ki jagah signal bhejein
                    order_refund_requested.send(
                        sender=Order, 
                        order_id=order.id, 
                        # Amount calculate karke bhejein
                        amount=order.final_amount, 
                        reason="Cancelled by customer."
                    )
                    logger.info(f"Refund request signal sent for cancelled order {order.id}.")
                # ----------------------------------

            return Response({"status": "Order cancelled and refund initiated if applicable."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error cancelling order {order.id}: {e}")
            return Response({"detail": "Failed to cancel order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrderHistoryAPIView(generics.ListAPIView):
    """
    Customer ke puraane orders ki list.
    GET /api/v1/orders/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        # Sirf usi customer ke orders dikhayein jo logged in hai
        return Order.objects.filter(customer=self.request.user)


class OrderDetailAPIView(generics.RetrieveAPIView):
    """
    Ek specific order ki poori detail.
    GET /api/v1/orders/<uuid:id>/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderSerializer
    lookup_field = 'id' # URL se 'id' parameter lega

    def get_queryset(self):
        # Customer sirf apne hi orders dekh sakta hai
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items__sku', 'timeline'
        )


class CancelOrderAPIView(APIView):
    """
    Customer khud order cancel kar sake.
    POST /api/v1/orders/<id>/cancel/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, id):
        # Order dhoondhein jo sirf isi customer ka ho
        order = get_object_or_404(Order, id=id, customer=request.user)
        
        # Sirf 'pending' ya 'confirmed' order hi cancel ho sakte hain
        if order.status not in ['pending', 'confirmed']:
            return Response(
                {"detail": "Cannot cancel order at this stage (already processing)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                order.status = 'cancelled'
                order.save(update_fields=['status'])
                
                # Timeline update
                OrderTimeline.objects.create(
                    order=order, 
                    status='cancelled', 
                    notes="Cancelled by customer."
                )
                
                # --- AUTO REFUND LOGIC ---
                if order.payment_status == 'paid':
                    process_order_refund(order, reason="Cancelled by customer")
                # -------------------------

            return Response({"status": "Order cancelled and refund initiated if applicable."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error cancelling order {order.id}: {e}")
            return Response({"detail": "Failed to cancel order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)