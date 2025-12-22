# apps/payments/views.py

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .services import PaymentService


class CreatePaymentIntentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        intent = PaymentService.create_intent(
            user=request.user,
            order_id=request.data["order_id"],
            method=request.data["payment_method"],
        )
        return Response(
            {
                "gateway_order_id": intent.gateway_order_id,
                "amount": intent.amount,
                "currency": intent.currency,
            },
            status=status.HTTP_201_CREATED,
        )


class RazorpayWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get("X-Razorpay-Signature")
        if not signature:
            return Response(status=400)

        if not PaymentService.verify_webhook_signature(request.body, signature):
            return Response(status=403)

        PaymentService.process_webhook(request.data)
        return Response({"status": "ok"})
