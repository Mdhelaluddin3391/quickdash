# apps/payments/views.py
import json
import logging
import razorpay

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

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
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        payload = json.loads(body_str)
        event_id = payload.get("id")
        if WebhookEvent.objects.filter(event_id=event_id).exists():
            return JsonResponse({"status": "already_processed"})
        
        with transaction.atomic():
            WebhookEvent.objects.create(event_id=event_id)

        if not razorpay_client:
            return Response({"detail": "Payment gateway unavailable."}, status=503)

        serializer = CreatePaymentIntentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.context["order"]

        if order.customer != request.user:
            return Response({"detail": "Permission denied."}, status=403)

        try:
            gateway_order_id = create_razorpay_order(order, order.final_amount)
        except Exception as e:
            logger.error(f"Razorpay Order Create Error: {e}")
            return Response({"detail": "Gateway error."}, status=500)

        intent = PaymentIntent.objects.create(
            order=order,
            gateway_order_id=gateway_order_id,
            amount=order.final_amount,
            currency="INR",
            status=PaymentIntent.IntentStatus.PENDING,
        )

        return Response(PaymentIntentSerializer(intent).data, status=201)


class VerifyPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        serializer = VerifyPaymentSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        intent = serializer.context["payment_intent"]
        order = intent.order

        ok = verify_payment_signature(
            order_id=str(order.id),
            gateway_order_id=data["gateway_order_id"],
            gateway_payment_id=data["gateway_payment_id"],
            gateway_signature=data["gateway_signature"],
        )

        if not ok:
            logger.warning(f"Signature Mismatch for Order {order.id}")
            intent.status = PaymentIntent.IntentStatus.FAILED
            intent.save()
            return Response({"detail": "Invalid signature."}, status=400)

        # Idempotent Success Handling
        with transaction.atomic():
            intent.status = PaymentIntent.IntentStatus.PAID
            intent.gateway_payment_id = data["gateway_payment_id"]
            intent.save()

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
                payment.save()

        # Signal outside atomic block (or on_commit if configured)
        payment_succeeded.send(sender=PaymentIntent, order=order)

        return Response({"status": "success", "order_id": str(order.id)})


@method_decorator(csrf_exempt, name="dispatch")
class RazorpayWebhookView(View):
    """
    Handles 'payment.captured' events from Razorpay.
    """
    @method_decorator(csrf_exempt, name="dispatch")
    def post(self, request, *args, **kwargs):
        webhook_secret = getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "")
        signature = request.headers.get("X-Razorpay-Signature")

        if not webhook_secret or not signature:
            return JsonResponse({"error": "Configuration missing"}, status=500)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            body_str = request.body.decode("utf-8")
            client.utility.verify_webhook_signature(body_str, signature, webhook_secret)
            
            payload = json.loads(body_str)
            event_type = payload.get("event")
            event_id = payload.get("id")

            # FIX: Event-Level Idempotency using IdempotencyKey
            from apps.warehouse.models import IdempotencyKey
            from datetime import timedelta
            
            # Check if this specific webhook event ID was already processed
            if IdempotencyKey.objects.filter(key=event_id).exists():
                logger.info(f"Webhook event {event_id} already processed. Skipping.")
                return JsonResponse({"status": "already_processed"})

            if event_type == "payment.captured":
                entity = payload["payload"]["payment"]["entity"]
                gateway_order_id = entity["order_id"]
                gateway_payment_id = entity["id"]

                intent = PaymentIntent.objects.filter(gateway_order_id=gateway_order_id).first()
                if not intent:
                    logger.critical(f"Webhook: Payment {gateway_payment_id} captured but NO INTENT found for Order {gateway_order_id}")
                    return JsonResponse({"error": "Intent not found"}, status=400)

                order = intent.order

                with transaction.atomic():
                    # Mark event as processed immediately to prevent race conditions
                    IdempotencyKey.objects.create(
                        key=event_id,
                        route="razorpay_webhook",
                        expires_at=timezone.now() + timedelta(days=7),
                        response_status=200
                    )

                    Payment.objects.get_or_create(
                        transaction_id=gateway_payment_id,
                        defaults={
                            "order": order,
                            "user": order.customer,
                            "payment_method": Payment.PaymentMethod.RAZORPAY,
                            "amount": intent.amount,
                            "currency": entity.get("currency", "INR"),
                            "status": Payment.PaymentStatus.SUCCESSFUL,
                            "gateway_order_id": gateway_order_id,
                            "gateway_response": entity,
                        }
                    )
                    
                    if intent.status != PaymentIntent.IntentStatus.PAID:
                        intent.status = PaymentIntent.IntentStatus.PAID
                        intent.save()

                logger.info(f"Webhook: Payment {gateway_payment_id} synced for Order {order.id}")

            return JsonResponse({"status": "ok"})

        except Exception as e:
            logger.exception(f"Webhook Error: {e}")
            return JsonResponse({"error": str(e)}, status=400)