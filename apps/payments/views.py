# apps/payments/views.py
import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

import razorpay
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer
from .models import PaymentIntent, Payment
from .serializers import (
    CreatePaymentIntentSerializer,
    VerifyPaymentSerializer,
    PaymentIntentSerializer,
)
from .signals import payment_succeeded
from .services import razorpay_client, create_razorpay_order, verify_payment_signature

logger = logging.getLogger(__name__)


class CreatePaymentIntentAPIView(APIView):
    """
    Step 1: Customer sends order_id, we create Razorpay Order & PaymentIntent.

    POST /api/v1/payments/create-intent/
    body: { "order_id": "..." }
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        if not razorpay_client:
            return Response(
                {"detail": "Payment gateway is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = CreatePaymentIntentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.context["order"]

        try:
            gateway_order_id = create_razorpay_order(order, order.final_amount)
        except Exception as e:
            logger.error(
                "Error creating Razorpay order for Order %s: %s",
                order.id,
                e,
            )
            return Response(
                {"detail": f"Payment gateway error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        intent = PaymentIntent.objects.create(
            order=order,
            gateway_order_id=gateway_order_id,
            amount=order.final_amount,
            currency="INR",
            status=PaymentIntent.IntentStatus.PENDING,
        )

        response_serializer = PaymentIntentSerializer(intent)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class VerifyPaymentAPIView(APIView):
    """
    Step 2: Frontend sends Razorpay payment details, we verify signature
    and mark PaymentIntent paid.

    POST /api/v1/payments/verify/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        if not razorpay_client:
            return Response(
                {"detail": "Payment gateway is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = VerifyPaymentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intent = serializer.context["payment_intent"]
        order = intent.order

        # Signature verify
        ok = verify_payment_signature(
            order_id=str(order.id),
            gateway_order_id=data["gateway_order_id"],
            gateway_payment_id=data["gateway_payment_id"],
            gateway_signature=data["gateway_signature"],
        )

        if not ok:
            logger.warning(
                "Payment verification FAILED for Order %s. Signature mismatch.",
                order.id,
            )
            intent.status = PaymentIntent.IntentStatus.FAILED
            intent.save(update_fields=["status"])
            return Response(
                {"detail": "Payment verification failed. Invalid signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Signature OK: mark intent + create Payment (idempotent)
        with transaction.atomic():
            intent.status = PaymentIntent.IntentStatus.PAID
            intent.gateway_payment_id = data["gateway_payment_id"]
            intent.save(update_fields=["status", "gateway_payment_id"])

            # Idempotent Payment creation
            payment, created = Payment.objects.get_or_create(
                transaction_id=data["gateway_payment_id"],
                defaults={
                    "order": order,
                    "user": request.user,
                    "payment_method": Payment.PaymentMethod.RAZORPAY,
                    "amount": intent.amount,
                    "currency": intent.currency,
                    "status": Payment.PaymentStatus.SUCCESSFUL,
                    "gateway_order_id": data["gateway_order_id"],
                },
            )
            if not created and payment.status != Payment.PaymentStatus.SUCCESSFUL:
                payment.status = Payment.PaymentStatus.SUCCESSFUL
                payment.gateway_order_id = data["gateway_order_id"]
                payment.save(update_fields=["status", "gateway_order_id"])

        # Inform Orders app via signal
        try:
            payment_succeeded.send(sender=PaymentIntent, order=order)
            logger.info("Sent payment_succeeded signal for order %s", order.id)
        except Exception as e:
            logger.error(
                "Error sending payment_succeeded signal for order %s: %s",
                order.id,
                e,
            )

        return Response(
            {
                "status": "success",
                "order_id": str(order.id),
                "payment_status": "paid",
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(View):
    """
    Razorpay webhook endpoint.

    Configure URL + secret in Razorpay dashboard.

    - Verifies webhook signature.
    - On `payment.captured`, ensures Payment row is marked SUCCESSFUL.
    """
    def post(self, request, *args, **kwargs):
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
        webhook_signature = request.headers.get("X-Razorpay-Signature")

        if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
            return JsonResponse(
                {"error": "Razorpay not configured."},
                status=503,
            )

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            body = request.body.decode("utf-8")
            client.utility.verify_webhook_signature(
                body,
                webhook_signature,
                webhook_secret,
            )

            payload = json.loads(body)
            event = payload.get("event")

            if event == "payment.captured":
                payment_entity = payload["payload"]["payment"]["entity"]
                gateway_order_id = payment_entity["order_id"]
                gateway_payment_id = payment_entity["id"]

                # Try to relate back to PaymentIntent and Payment
                try:
                    intent = PaymentIntent.objects.filter(
                        gateway_order_id=gateway_order_id
                    ).order_by("-created_at")[0]
                    order = intent.order
                except IndexError:
                    intent = None
                    order = None

                payment, created = Payment.objects.get_or_create(
                    transaction_id=gateway_payment_id,
                    defaults={
                        "order": order,
                        "user": getattr(order, "customer", None)
                        if order
                        else None,
                        "payment_method": Payment.PaymentMethod.RAZORPAY,
                        "amount": (
                            intent.amount
                            if intent is not None
                            else payment_entity["amount"] / 100
                        ),
                        "currency": payment_entity.get("currency", "INR"),
                        "status": Payment.PaymentStatus.SUCCESSFUL,
                        "gateway_order_id": gateway_order_id,
                        "gateway_response": payment_entity,
                    },
                )
                if not created:
                    payment.status = Payment.PaymentStatus.SUCCESSFUL
                    payment.gateway_order_id = gateway_order_id
                    payment.gateway_response = payment_entity
                    payment.save(
                        update_fields=[
                            "status",
                            "gateway_order_id",
                            "gateway_response",
                            "updated_at",
                        ]
                    )

                logger.info(
                    "Webhook: Payment Successful for gateway_order %s / pay %s",
                    gateway_order_id,
                    gateway_payment_id,
                )

            return JsonResponse({"status": "ok"})

        except Exception as e:
            logger.exception("Webhook Error: %s", e)
            return JsonResponse({"error": str(e)}, status=400)
