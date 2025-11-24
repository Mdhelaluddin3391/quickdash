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
from django.db import models
from apps.accounts.permissions import IsCustomer  # Added Import
from apps.payments.models import Payment
from .models import Order, Cart, CartItem
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    OrderListSerializer,
    CartSerializer,
    AddToCartSerializer,
    PaymentVerificationSerializer,
    CancelOrderSerializer,
)
from .services import (
    create_order_from_cart,
    process_successful_payment,
    cancel_order,
)

logger = logging.getLogger(__name__)

# =========================================================
# Cart Views
# =========================================================

class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

class AddToCartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sku_id = serializer.validated_data["sku_id"]
        qty = serializer.validated_data["quantity"]

        cart, _ = Cart.objects.get_or_create(customer=request.user)

        if qty == 0:
            CartItem.objects.filter(cart=cart, sku_id=sku_id).delete()
        else:
            item, _ = CartItem.objects.get_or_create(cart=cart, sku_id=sku_id)
            item.quantity = qty
            item.save()

        cart.refresh_from_db()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

# =========================================================
# Checkout / Payment Views
# =========================================================

class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Create Order from Cart
        order, payment, err = create_order_from_cart(
            user=request.user,
            warehouse_id=data["warehouse_id"],
            delivery_address_json=data["delivery_address_json"],
            delivery_lat=data.get("delivery_lat"),
            delivery_lng=data.get("delivery_lng"),
            payment_method=data.get("payment_method", "RAZORPAY"),
        )

        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        # COD → straight confirm
        if data.get("payment_method") == "COD":
            ok, msg = process_successful_payment(order)
            if not ok:
                return Response(
                    {"error": "Failed to confirm COD order", "detail": msg},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            # Clear cart
            Cart.objects.filter(customer=request.user).delete()
            return Response(
                {
                    "order": OrderSerializer(order).data,
                    "payment": {"mode": "COD", "status": "CONFIRMED"},
                },
                status=status.HTTP_201_CREATED,
            )

        # Online payment (Razorpay)
        try:
            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )
            amount_paise = int(float(order.final_amount) * 100)
            rzp_order = client.order.create(
                dict(
                    amount=amount_paise,
                    currency="INR",
                    payment_capture=1,
                    notes={"order_id": str(order.id)},
                )
            )
        except Exception as e:
            logger.error(f"Razorpay Error: {e}")
            return Response({"error": "Payment Gateway Error"}, status=500)

        # Update Payment Record
        if not payment:
            payment = Payment.objects.create(
                order=order,
                amount=order.final_amount,
                payment_method=Payment.PaymentMethod.RAZORPAY,
                gateway_order_id=rzp_order["id"],
            )
        else:
            payment.gateway_order_id = rzp_order["id"]
            payment.save(update_fields=["gateway_order_id"])

        order.payment_gateway_order_id = rzp_order["id"]
        order.save(update_fields=["payment_gateway_order_id"])

        return Response(
            {
                "order_id": str(order.id),
                "razorpay_order_id": rzp_order["id"],
                "amount": str(order.final_amount),
                "currency": "INR",
            },
            status=status.HTTP_201_CREATED,
        )

class PaymentVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        try:
            client.utility.verify_payment_signature({
                "razorpay_order_id": data["razorpay_order_id"],
                "razorpay_payment_id": data["razorpay_payment_id"],
                "razorpay_signature": data["razorpay_signature"],
            })
        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Invalid signature"}, status=400)

        payment = get_object_or_404(Payment, gateway_order_id=data["razorpay_order_id"])

        if payment.order.customer_id != request.user.id:
            return Response({"error": "Forbidden"}, status=403)

        payment.transaction_id = data["razorpay_payment_id"]
        payment.status = Payment.PaymentStatus.SUCCESSFUL
        payment.save()

        process_successful_payment(payment.order)
        Cart.objects.filter(customer=request.user).delete()

        return Response({"status": "success", "order": OrderSerializer(payment.order).data})

# =========================================================
# Orders ViewSet
# =========================================================

class IsOrderOwnerOrStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.is_staff or obj.customer_id == request.user.id

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsOrderOwnerOrStaff]
    serializer_class = OrderSerializer
    # N+1 Fix: Added prefetch_related/select_related
    queryset = Order.objects.select_related("customer", "warehouse") \
                            .prefetch_related("items", "timeline").all()

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        
        # Cancellation Window Check
        window_seconds = getattr(settings, "ORDER_CANCELLATION_WINDOW", 300)
        if not request.user.is_staff:
            cutoff = order.created_at + timedelta(seconds=window_seconds)
            if timezone.now() > cutoff:
                return Response({"error": "Cancellation window expired"}, status=400)

        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")

        ok, msg = cancel_order(order, cancelled_by="CUSTOMER", reason=reason)
        if not ok:
            return Response({"error": msg}, status=400)

        return Response(OrderSerializer(order).data)