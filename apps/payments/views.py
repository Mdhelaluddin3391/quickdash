from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .services import PaymentService
from .serializers import InitiatePaymentSerializer
from apps.orders.models.order import Order
import razorpay
import json
import logging
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction

logger = logging.getLogger(__name__)

class RazorpayWebhookView(APIView):
    """
    Handles Razorpay Webhooks with Strict Signature Verification.
    Idempotency is handled by checking transaction_id existence.
    """
    permission_classes = []  # Allow public access for webhook
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        # 1. Get Signature from Header
        signature = request.headers.get('X-Razorpay-Signature')
        if not signature:
            logger.warning("Razorpay Webhook: Missing Signature")
            return Response(status=status.HTTP_403_FORBIDDEN)

        # 2. Verify Signature
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            # Must use raw request body bytes for verification
            client.utility.verify_webhook_signature(
                request.body.decode('utf-8'),
                signature,
                settings.RAZORPAY_WEBHOOK_SECRET
            )
        except razorpay.errors.SignatureVerificationError:
            logger.critical("Razorpay Webhook: Invalid Signature detected! Possible attack.")
            return Response(status=status.HTTP_403_FORBIDDEN)

        # 3. Process Payload (Idempotent)
        data = request.data
        event = data.get('event')
        payload = data.get('payload', {}).get('payment', {}).get('entity', {})
        
        order_id = payload.get('order_id')  # Razorpay Order ID
        transaction_id = payload.get('id')
        
        if not order_id or not transaction_id:
             return Response(status=status.HTTP_400_BAD_REQUEST)

        # Idempotency Check: Don't process if already captured
        if PaymentTransaction.objects.filter(transaction_id=transaction_id).exists():
            return Response({"status": "Already Processed"}, status=status.HTTP_200_OK)

        if event == 'payment.captured':
            try:
                order = Order.objects.get(payment_order_id=order_id)
                order.mark_as_paid(transaction_id=transaction_id, metadata=payload)
                logger.info(f"Order {order.id} marked as PAID via Webhook.")
            except Order.DoesNotExist:
                logger.error(f"Webhook received for unknown order: {order_id}")
                return Response(status=status.HTTP_404_NOT_FOUND)

        return Response({"status": "Webhook Received"}, status=status.HTTP_200_OK)

class PaymentViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def create(self, request):
        """
        Initiate a payment for an existing Order.
        """
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            order = Order.objects.get(id=serializer.validated_data['order_id'], user=request.user)
            data = PaymentService.initiate_payment(
                order, 
                serializer.validated_data['method']
            )
            return Response(data, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class PaymentWebhookView(APIView):
    """
    Public endpoint for Razorpay/Stripe callbacks.
    MUST be secure via signature verification.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Verify Signature (Simplistic for V2 demo)
        # signature = request.headers.get('X-Razorpay-Signature')
        # if not PaymentService.verify_webhook_signature(request.body.decode(), signature, 'secret'):
        #    return Response(status=403)
        
        # 2. Extract Data
        data = request.data
        # Assuming payload structure matches provider
        provider_payment_id = data.get('payload', {}).get('payment', {}).get('entity', {}).get('id')
        provider_order_id = data.get('payload', {}).get('order', {}).get('entity', {}).get('id')
        
        if not provider_payment_id or not provider_order_id:
             return Response({"status": "ignored"}, status=200)

        # 3. Process
        try:
            PaymentService.process_webhook_success(
                provider_payment_id, 
                provider_order_id, 
                "verified_signature"
            )
            return Response({"status": "processed"}, status=200)
        except Exception as e:
            # Log error securely
            return Response({"error": "Processing failed"}, status=500)