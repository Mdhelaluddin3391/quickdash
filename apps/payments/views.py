# apps/payments/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import CreatePaymentIntentSerializer, PaymentIntentSerializer
from .services import PaymentService
from apps.utils.exceptions import BusinessLogicException


class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        intent = PaymentService.create_intent(
            user=request.user,
            order_id=serializer.validated_data["order_id"],
            method=serializer.validated_data["payment_method"],
        )
        return Response(
            PaymentIntentSerializer(intent).data,
            status=status.HTTP_201_CREATED,
        )


class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get("X-Razorpay-Signature")
        if not signature:
            return Response(status=400)

        if not PaymentService.verify_webhook_signature(
            request.body,
            signature,
        ):
            return Response(status=403)

        PaymentService.process_webhook(request.data)
        return Response({"status": "ok"})
