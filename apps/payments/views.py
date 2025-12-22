from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny

from .serializers import CreatePaymentIntentSerializer, PaymentIntentSerializer
from .services import PaymentService
from apps.utils.exceptions import BusinessLogicException

class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            intent = PaymentService.create_intent(
                user=request.user,
                order_id=serializer.validated_data['order_id'],
                method=serializer.validated_data['payment_method']
            )
            return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)
        except BusinessLogicException as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class RazorpayWebhookView(APIView):
    """
    Public webhook endpoint. Secure via Signature Verification.
    """
    permission_classes = [AllowAny]
    authentication_classes = [] # Disable auth for webhooks

    def post(self, request):
        signature = request.headers.get('X-Razorpay-Signature')
        body = request.body.decode('utf-8')

        # 1. Security Check
        if not signature or not PaymentService.verify_webhook_signature(body, signature):
            return Response({"detail": "Invalid Signature"}, status=status.HTTP_403_FORBIDDEN)

        # 2. Process
        try:
            PaymentService.process_webhook(request.data)
            return Response({"status": "ok"}, status=status.HTTP_200_OK)
        except Exception as e:
            # Log but return 200/500 depending on retry strategy. 
            # Usually 200 if logic fail, 500 if infra fail.
            return Response({"status": "error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)