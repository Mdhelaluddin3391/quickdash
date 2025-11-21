import logging
import razorpay

from django.db import transaction
from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer
from apps.delivery.models import DeliveryTask
from .models import Cart, Order, OrderItem
from apps.payments.models import Payment
from apps.warehouse.models import PickingTask, PickItem
from .serializers import (
    CreateOrderSerializer,
    PaymentVerificationSerializer,
)
from rest_framework import viewsets
from rest_framework import filters
from .serializers import OrderSerializer, OrderListSerializer
from .models import Order
from apps.payments.signals import payment_succeeded
from .services import process_successful_payment

logger = logging.getLogger(__name__)


# moved payment confirmation logic to `services.process_successful_payment`



class CheckoutView(generics.GenericAPIView):
    """
    Handles the checkout process, creates a pending order, and initiates payment.
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CreateOrderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        data = serializer.validated_data
        payment_method = data.get('payment_method', 'RAZORPAY')
        
        # Delegate order creation to service layer
        try:
            order, payment, err = create_order_from_cart(
                user=user,
                warehouse_id=data.get('warehouse_id'),
                delivery_address_json=data.get('delivery_address_json'),
                delivery_lat=data.get('delivery_lat'),
                delivery_lng=data.get('delivery_lng'),
                payment_method=payment_method,
            )
            if err:
                return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Error creating order for user %s: %s", user.id if user else 'unknown', e)
            return Response({"error": "Could not create order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if payment_method == 'COD':
            # For COD we created a payment in service; if not present, create one
            if not payment:
                from apps.payments.models import Payment as PaymentModel
                payment = PaymentModel.objects.create(order=order, payment_method='COD', amount=order.final_amount)
            success, msg = process_successful_payment(order)
            if success:
                return Response({"message": "Order Confirmed (COD)", "order_id": order.id}, status=status.HTTP_201_CREATED)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        elif payment_method == 'RAZORPAY':
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                rzp_order = client.order.create({
                    'amount': int(order.final_amount * 100),
                    'currency': 'INR',
                    'receipt': str(order.id)
                })

                Payment.objects.create(
                    order=order,
                    payment_method='RAZORPAY',
                    amount=order.final_amount,
                    gateway_order_id=rzp_order['id']
                )

                return Response({
                    "razorpay_order_id": rzp_order['id'],
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": int(order.final_amount * 100),
                    "order_id": order.id
                })
            except Exception as e:
                logger.exception(f"Razorpay client error for order {order.id if 'order' in locals() else 'unknown'}: {e}")
                return Response({"error": "Payment gateway error."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({"error": "Invalid payment method"}, status=status.HTTP_400_BAD_REQUEST)


class PaymentVerificationView(APIView):
    """
    Verifies the Razorpay payment signature and confirms the order.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentVerificationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            client.utility.verify_payment_signature(data)
            
            payment = get_object_or_404(Payment, gateway_order_id=data['razorpay_order_id'])
            payment.transaction_id = data['razorpay_payment_id']
            payment.save()
            
            success, msg = process_successful_payment(payment.order)
            if success:
                return Response({"status": "Payment Successful, Order Confirmed"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Razorpay signature verification failed for order {data.get('razorpay_order_id')}")
            return Response({"error": "Invalid payment signature"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Payment verification failed: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only endpoints for Orders: list and retrieve for customers."""
    queryset = Order.objects.all().select_related('customer', 'warehouse')
    serializer_class = OrderSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at', 'final_amount']
    search_fields = ['id', 'status']

    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user and user.is_authenticated:
            # Customers only see their orders
            return qs.filter(customer=user)
        return qs.none()
