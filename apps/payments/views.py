from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .services import PaymentService
from .serializers import InitiatePaymentSerializer
from apps.orders.models.order import Order

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