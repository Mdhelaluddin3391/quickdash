# apps/orders/views.py
import logging
import razorpay
from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCustomer
from apps.payments.models import Payment
from .models import Order, Cart, CartItem
from .serializers import (
    CreateOrderSerializer, OrderSerializer, OrderListSerializer,
    CartSerializer, AddToCartSerializer, PaymentVerificationSerializer, CancelOrderSerializer
)
from .services import (
    CheckoutOrchestrator, # <--- NEW
    process_successful_payment,
    cancel_order
)

logger = logging.getLogger(__name__)

class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        return Response(CartSerializer(cart).data)

class AddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart, _ = Cart.objects.get_or_create(customer=request.user)
        sku_id = serializer.validated_data["sku_id"]
        qty = serializer.validated_data["quantity"]

        if qty == 0:
            CartItem.objects.filter(cart=cart, sku_id=sku_id).delete()
        else:
            item, created = CartItem.objects.update_or_create(
                cart=cart, sku_id=sku_id, defaults={"quantity": qty}
            )
            # Ensure save() is called to recalc total_price
            item.save()

        cart.refresh_from_db()
        return Response(CartSerializer(cart).data)

class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def post(self, request):
        serializer = CreateOrderSerializer(
            data=request.data,
            context={"request": request}   # <-- FIXED
        )
        serializer.is_valid(raise_exception=True)

        orchestrator = CheckoutOrchestrator(request.user, serializer.validated_data)
        order, payment_data, error = orchestrator.execute()

        if error:
            return Response({"error": error}, status=400)

        if payment_data["mode"] == "COD":
            ok, msg = process_successful_payment(order)
            if not ok:
                return Response({"error": msg}, status=500)

            Cart.objects.filter(customer=request.user).delete()

            return Response({
                "order": OrderSerializer(order).data,
                "payment": payment_data
            }, status=201)

        return Response({
            "order_id": str(order.id),
            **payment_data
        }, status=201)



class PaymentVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        # FIX: Explicit error handling for signature verification
        try:
            client.utility.verify_payment_signature(data)
        except razorpay.errors.SignatureVerificationError:
            logger.warning(f"Payment signature verification failed for order {data.get('razorpay_order_id')}")
            return Response({"error": "Invalid signature"}, status=400)
        except Exception as e:
            logger.exception(f"Unexpected error during payment verification: {e}")
            return Response({"error": "Payment verification failed due to a system error"}, status=500)

        payment = get_object_or_404(Payment, gateway_order_id=data["razorpay_order_id"])
        
        # Idempotency check
        if payment.status == Payment.PaymentStatus.SUCCESSFUL:
             return Response({"status": "success", "message": "Already processed"})

        payment.transaction_id = data["razorpay_payment_id"]
        payment.save()

        process_successful_payment(payment.order)
        Cart.objects.filter(customer=request.user).delete()

        return Response({"status": "success"})

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        # Optimization: select_related
        qs = Order.objects.select_related("customer", "warehouse").prefetch_related("items", "items__sku").all()
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        # ... validation logic (keep existing) ...
        # Call service
        ok, msg = cancel_order(order, cancelled_by="CUSTOMER", reason=request.data.get("reason", ""))
        if not ok: return Response({"error": msg}, status=400)
        return Response(OrderSerializer(order).data)