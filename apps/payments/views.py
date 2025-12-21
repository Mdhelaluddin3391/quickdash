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
        # FIX: Removed erroneous 'body_str' usage and WebhookEvent check.
        # This is a client request, not a webhook callback.
        
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

        # 1. Cryptographic Signature Verification
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

        # 2. Atomic Status Update & Payment Recording
        try:
            with transaction.atomic():
                # Lock Intent Row to prevent race with Webhook
                intent = PaymentIntent.objects.select_for_update().get(id=intent.id)
                
                if intent.status == PaymentIntent.IntentStatus.PAID:
                    return Response({"status": "success", "order_id": str(order.id)})

                intent.status = PaymentIntent.IntentStatus.PAID
                intent.gateway_payment_id = data["gateway_payment_id"]
                intent.save()

                # Create Payment Record
                payment, _ = Payment.objects.get_or_create(
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
                
                # 3. Trigger Order Confirmation (Inventory/Notification)
                from apps.orders.services import process_successful_payment
                success, msg = process_successful_payment(order)
                if not success:
                    raise Exception(f"Order Processing Failed: {msg}")

            return Response({"status": "success", "order_id": str(order.id)})

        except Exception as e:
            logger.error(f"Payment Verification Transaction Failed: {e}")
            return Response({"detail": "Processing error after payment."}, status=500)


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
            # 1. Verify Signature first to reject spoofed requests
            client.utility.verify_webhook_signature(body_str, signature, webhook_secret)
            
            payload = json.loads(body_str)
            event_type = payload.get("event")
            event_id = payload.get("id")

            # 2. Atomic Idempotency Check
            from apps.warehouse.models import IdempotencyKey
            from datetime import timedelta
            
            with transaction.atomic():
                # Try to acquire a lock on this event_id
                idem_key, created = IdempotencyKey.objects.select_for_update().get_or_create(
                    key=event_id,
                    defaults={
                        "route": "razorpay_webhook",
                        "expires_at": timezone.now() + timedelta(days=7),
                        "response_status": 200
                    }
                )
                
                # If key existed, we have processed this. Return 200 to silence Razorpay.
                if not created:
                    logger.info(f"Webhook event {event_id} replay detected.")
                    return JsonResponse({"status": "already_processed"})

                # 3. Process Logic
                if event_type == "payment.captured":
                    entity = payload["payload"]["payment"]["entity"]
                    gateway_order_id = entity["order_id"]
                    gateway_payment_id = entity["id"]

                    # Lock the intent to prevent race with the Frontend 'VerifyPayment' API
                    intent = PaymentIntent.objects.select_for_update().filter(
                        gateway_order_id=gateway_order_id
                    ).first()
                    
                    if not intent:
                        logger.critical(f"Webhook: Orphaned Payment {gateway_payment_id} for Order {gateway_order_id}")
                        return JsonResponse({"status": "intent_missing"})

                    order = intent.order

                    # Create Payment record idempotently
                    payment, pay_created = Payment.objects.get_or_create(
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

                    # Update Intent and Order status
                    if intent.status != PaymentIntent.IntentStatus.PAID:
                        intent.status = PaymentIntent.IntentStatus.PAID
                        intent.save(update_fields=['status'])
                        
                        # Trigger Order Success Logic
                        from apps.orders.services import process_successful_payment
                        process_successful_payment(order)

                        logger.info(f"Webhook: Payment {gateway_payment_id} confirmed Order {order.id}")

            return JsonResponse({"status": "ok"})

        except Exception as e:
            logger.exception(f"Webhook Error: {e}")
            return JsonResponse({"error": str(e)}, status=400)