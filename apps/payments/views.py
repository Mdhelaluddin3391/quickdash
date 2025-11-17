from django.shortcuts import render

# Create your views here.
import razorpay
import logging
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Hamare apne apps se import
from apps.accounts.permissions import IsCustomer
# FIX: Order aur Timeline ke imports hata diye
# from apps.orders.models import Order, OrderTimeline
# FIX: Warehouse signal ka import hata diya
# from apps.warehouse.signals import send_order_created
from .models import PaymentIntent
from .serializers import (
    CreatePaymentIntentSerializer,
    VerifyPaymentSerializer,
    PaymentIntentSerializer,
)
# FIX: Apna naya signal import kiya
from .signals import payment_succeeded


logger = logging.getLogger(__name__)

# ===================================================================
#                      RAZORPAY CLIENT SETUP
# ===================================================================

try:
    razorpay_client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    logger.info("Razorpay client initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Razorpay client: {e}")
    razorpay_client = None

# ===================================================================
#                      PAYMENT VIEWS
# ===================================================================

class CreatePaymentIntentAPIView(APIView):
    """
    Customer se Order ID leta hai aur Razorpay payment link banata hai.
    POST /api/v1/payments/create-intent/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        if not razorpay_client:
            return Response(
                {"detail": "Payment gateway is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        serializer = CreatePaymentIntentSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        order = serializer.context['order']
        amount_in_paise = int(order.final_amount * 100) # Razorpay paise mein amount leta hai

        try:
            # Step 1: Razorpay par order create karein
            razorpay_order_data = {
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": str(order.id),
                "notes": {
                    "order_id": str(order.id),
                    "customer_phone": order.customer.phone
                }
            }
            gateway_order = razorpay_client.order.create(data=razorpay_order_data)
            
            # Step 2: Hamare database mein PaymentIntent banayein
            payment_intent = PaymentIntent.objects.create(
                order=order,
                gateway_order_id=gateway_order['id'],
                amount=order.final_amount,
                status="pending"
            )
            
            # Step 3: Customer ko details waapas bhejein
            response_serializer = PaymentIntentSerializer(payment_intent)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error creating Razorpay order for Order {order.id}: {e}")
            return Response(
                {"detail": f"Payment gateway error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPaymentAPIView(APIView):
    """
    Customer ke payment ko Razorpay se verify karta hai.
    POST /api/v1/payments/verify/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        serializer = VerifyPaymentSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        intent = serializer.context['payment_intent']
        order = intent.order

        try:
            # Step 1: Razorpay signature ko verify karein
            razorpay_client.utility.verify_payment_signature({
                'razorpay_order_id': data['gateway_order_id'],
                'razorpay_payment_id': data['gateway_payment_id'],
                'razorpay_signature': data['gateway_signature']
            })
            
            # --- Signature VERIFIED! Payment Successful ---

            # Step 2: Database transaction shuru karein
            with transaction.atomic():
                # PaymentIntent ko "paid" mark karein
                intent.status = "paid"
                intent.gateway_payment_id = data['gateway_payment_id']
                intent.save()
                
                # FIX: Order ko "confirmed" mark karna HATA diya
                # order.status = "confirmed"
                # order.payment_status = "paid"
                # order.save()
                
                # FIX: Order ki history (timeline) mein entry daalna HATA diya
                # OrderTimeline.objects.create( ... )

            # --- Transaction (Database ka kaam) poora hua ---

            # Step 3: WMS (Warehouse) ko signal bhejna HATA diya
            # FIX: Ab hum 'orders' app ko batane ke liye signal bhejenge
            try:
                payment_succeeded.send(sender=PaymentIntent, order=order)
                logger.info(f"Sent payment_succeeded signal for order {order.id}")
            except Exception as e:
                logger.error(f"Error sending payment_succeeded signal for order {order.id}: {e}")
                # Note: Payment ho chuka hai, agar signal fail hota hai toh background job se retry karna hoga

            return Response(
                {"status": "success", "order_id": order.id, "payment_status": "paid"},
                status=status.HTTP_200_OK
            )

        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Payment verification FAILED for Order {order.id}. Signature mismatch.")
            # Signature FAILED
            intent.status = "failed"
            intent.save()
            return Response({"detail": "Payment verification failed. Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error verifying payment for Order {order.id}: {e}")
            return Response(
                {"detail": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )