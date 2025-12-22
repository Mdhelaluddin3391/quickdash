import json
import logging
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from .services import PaymentService
from .serializers import PaymentSuccessSerializer
from .models import WebhookEvent

logger = logging.getLogger(__name__)

class PaymentSuccessView(views.APIView):
    """
    Called by Frontend after Razorpay Modal success.
    Verifies signature and confirms order.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PaymentSuccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            PaymentService.process_payment_success(serializer.validated_data)
            return Response({"status": "Payment Verified"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(views.APIView):
    """
    Server-to-Server confirmation (Resilient against network drops on client).
    """
    permission_classes = [AllowAny] # Signature verification is the auth

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature')
        body = request.body
        
        # 1. Verify Signature
        try:
            PaymentService.verify_webhook_signature(body, signature)
        except Exception as e:
            logger.warning(f"Webhook Signature Failed: {e}")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        data = json.loads(body)
        event_id = data.get('event_id')
        
        # 2. Idempotency Check
        if WebhookEvent.objects.filter(event_id=event_id).exists():
            return Response(status=status.HTTP_200_OK)

        # 3. Process
        try:
            event_type = data.get('event')
            payload = data.get('payload', {}).get('payment', {}).get('entity', {})
            
            if event_type == 'payment.captured':
                PaymentService.process_payment_success({
                    'razorpay_order_id': payload.get('order_id'),
                    'razorpay_payment_id': payload.get('id'),
                    'razorpay_signature': None # Webhooks are trusted via header sig
                })
            
            # Log Event
            WebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
                payload=data,
                processed=True
            )
            return Response(status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Webhook Processing Error: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)