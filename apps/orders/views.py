import logging
from decimal import Decimal
import razorpay
import json

from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer
from apps.catalog.models import SKU
from apps.delivery.models import DeliveryTask
from .models import Cart, CartItem, Order, OrderItem, Payment, ORDER_STATUS_CHOICES, PAYMENT_STATUS_CHOICES
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    OrderListSerializer,
    PaymentVerificationSerializer,
)
from .signals import payment_succeeded

logger = logging.getLogger(__name__)


def process_successful_payment(order_id):
    """
    Confirms an order and triggers the warehouse process.
    """
    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id, status="pending")
            
            order.status = "confirmed"
            order.payment_status = "paid"
            order.save()

            payment = order.payments.first()
            if payment:
                payment.status = "successful"
                payment.save()

            DeliveryTask.objects.create(order=order, status=DeliveryTask.DeliveryStatus.PENDING_ASSIGNMENT)
            Cart.objects.filter(customer=order.customer).delete()

            if order.warehouse:
                picking_task = PickingTask.objects.create(
                    order_id=str(order.id),
                    warehouse=order.warehouse,
                    status='PENDING'
                )
                for item in order.items.all():
                    PickItem.objects.create(
                        task=picking_task,
                        sku=item.sku,
                        qty_to_pick=item.quantity
                    )
                logger.info(f"WMS Task created for Order {order_id}")
            
            # Trigger signal for other apps
            payment_succeeded.send(sender=Order, order=order)
            
            return True, "Success"

    except Order.DoesNotExist:
        logger.warning(f"Order {order_id} not found or already processed.")
        return False, "Order not found."
    except Exception as e:
        logger.error(f"Payment processing failed for order {order_id}: {e}")
        return False, str(e)



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
        
        try:
            cart = Cart.objects.get(customer=user)
            if not cart.items.exists():
                return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)
        except Cart.DoesNotExist:
             return Response({"error": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)

        item_subtotal = cart.total_amount
        delivery_fee = settings.BASE_DELIVERY_FEE
        final_total = item_subtotal + delivery_fee
        
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    customer=user,
                    warehouse_id=data.get('warehouse_id'),
                    delivery_address_json=data.get('delivery_address_json'),
                    total_amount=item_subtotal,
                    final_amount=final_total,
                    status="pending",
                    payment_status="pending"
                )
                
                items_to_create = [
                    OrderItem(
                        order=order,
                        sku=c_item.sku,
                        quantity=c_item.quantity,
                        unit_price=c_item.sku.sale_price
                    ) for c_item in cart.items.all()
                ]
                OrderItem.objects.bulk_create(items_to_create)

        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return Response({"error": "Could not create order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if payment_method == 'COD':
            Payment.objects.create(order=order, payment_method='COD', amount=final_total)
            success, msg = process_successful_payment(order.id)
            if success:
                return Response({"message": "Order Confirmed (COD)", "order_id": order.id}, status=status.HTTP_201_CREATED)
            return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        elif payment_method == 'RAZORPAY':
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                rzp_order = client.order.create({
                    'amount': int(final_total * 100),
                    'currency': 'INR',
                    'receipt': str(order.id)
                })
                
                Payment.objects.create(
                    order=order, 
                    payment_method='RAZORPAY',
                    amount=final_total,
                    gateway_order_id=rzp_order['id']
                )
                
                return Response({
                    "razorpay_order_id": rzp_order['id'],
                    "razorpay_key": settings.RAZORPAY_KEY_ID,
                    "amount": int(final_total * 100),
                    "order_id": order.id
                })
            except Exception as e:
                logger.error(f"Razorpay client error: {e}")
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
            
            success, msg = process_successful_payment(payment.order.id)
            if success:
                return Response({"status": "Payment Successful, Order Confirmed"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": msg}, status=status.HTTP_400_BAD_REQUEST)

        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Razorpay signature verification failed for order {data.get('razorpay_order_id')}")
            return Response({"error": "Invalid payment signature"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Payment verification failed: {e}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
