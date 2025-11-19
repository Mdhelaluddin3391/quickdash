# apps/payments/views.py
import razorpay
import logging
from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsCustomer
from .models import PaymentIntent
from .serializers import (
    CreatePaymentIntentSerializer,
    VerifyPaymentSerializer,
    PaymentIntentSerializer,
)
from .signals import payment_succeeded


logger = logging.getLogger(__name__)

# ===================================================================
#                      RAZORPAY CLIENT SETUP
# ===================================================================

try:
    # Ensure keys are available before initialization
    if settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        logger.info("Razorpay client initialized successfully.")
    else:
        logger.error("Razorpay keys missing in settings.")
        razorpay_client = None
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
                
            # --- Transaction (Database ka kaam) poora hua ---

            # Step 3: Orders app ko signal bhejein
            try:
                payment_succeeded.send(sender=PaymentIntent, order=order)
                logger.info(f"Sent payment_succeeded signal for order {order.id}")
            except Exception as e:
                logger.error(f"Error sending payment_succeeded signal for order {order.id}: {e}")

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


# apps/payments/views.py
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views import View
from django.conf import settings
import razorpay
from .models import Payment

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(View):
    def post(self, request, *args, **kwargs):
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            # 1. Signature Verify
            client.utility.verify_webhook_signature(
                request.body.decode('utf-8'),
                webhook_signature,
                webhook_secret
            )
            
            # 2. Event Process
            payload = json.loads(request.body)
            event = payload.get('event')
            
            if event == 'payment.captured':
                payment_entity = payload['payload']['payment']['entity']
                order_id = payment_entity['order_id'] # Razorpay Order ID
                
                # DB mein Payment dhundo
                try:
                    payment = Payment.objects.get(gateway_order_id=order_id)
                    if payment.status != 'SUCCESSFUL':
                        payment.status = 'SUCCESSFUL'
                        payment.transaction_id = payment_entity['id']
                        payment.save()
                        
                        # Yahan par aap Order Status bhi 'CONFIRMED' kar sakte hain
                        # aur 'reserve_stock_for_order' call kar sakte hain.
                        logger.info(f"Webhook: Payment Successful for Order {order_id}")
                        
                except Payment.DoesNotExist:
                    logger.error(f"Webhook: Payment not found for order {order_id}")

            return JsonResponse({'status': 'ok'})

        except Exception as e:
            logger.error(f"Webhook Error: {e}")
            return JsonResponse({'error': str(e)}, status=400)