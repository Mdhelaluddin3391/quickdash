import logging

from django.conf import settings
from django.shortcuts import get_object_or_404

import razorpay
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.shortcuts import get_object_or_404

from .services import create_order_from_cart, process_successful_payment, cancel_order
from .models import Cart, CartItem, Order

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
    """
    Cart se order create karta hai.
    - COD: turant confirm + WMS signal
    - Razorpay: RZP order create + Payment record, client se payment karao
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        warehouse_id = data["warehouse_id"]
        delivery_address_json = data["delivery_address_json"]
        delivery_lat = data.get("delivery_lat")
        delivery_lng = data.get("delivery_lng")
        payment_method = data.get("payment_method", "RAZORPAY")

        # Create Order from Cart
        order, payment, err = create_order_from_cart(
            user=request.user,
            warehouse_id=warehouse_id,
            delivery_address_json=delivery_address_json,
            delivery_lat=delivery_lat,
            delivery_lng=delivery_lng,
            payment_method=payment_method,
        )

        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        # COD → straight confirm
        if payment_method == "COD":
            ok, msg = process_successful_payment(order)
            if not ok:
                return Response(
                    {"error": "Failed to confirm COD order", "detail": msg},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Optionally cart clear
            try:
                Cart.objects.filter(customer=request.user).delete()
            except Exception:
                pass

            return Response(
                {
                    "order": OrderSerializer(order).data,
                    "payment": {"mode": "COD", "status": "CONFIRMED"},
                },
                status=status.HTTP_201_CREATED,
            )

        # Online payment (Razorpay)
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

        # Payment record (if not already from service)
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

        # Store PG order id on Order too (optional)
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
    """
    Razorpay payment verify endpoint.
    Client se RZP order_id, payment_id, signature aata hai.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        # Verify signature
        try:
            client.utility.verify_payment_signature(
                {
                    "razorpay_order_id": data["razorpay_order_id"],
                    "razorpay_payment_id": data["razorpay_payment_id"],
                    "razorpay_signature": data["razorpay_signature"],
                }
            )
        except razorpay.errors.SignatureVerificationError as e:
            logger.warning("Razorpay signature verification failed: %s", e)
            return Response(
                {"error": "Invalid payment signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Locate Payment
        payment = get_object_or_404(
            Payment, gateway_order_id=data["razorpay_order_id"]
        )

        # Extra safety: ensure current user owns this order
        if payment.order.customer_id != request.user.id:
            return Response(
                {"error": "Not allowed for this order"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Update Payment
        payment.transaction_id = data["razorpay_payment_id"]
        payment.status = Payment.PaymentStatus.SUCCESSFUL
        payment.save(update_fields=["transaction_id", "status"])

        # Process success flow
        ok, msg = process_successful_payment(payment.order)
        if not ok:
            return Response(
                {"error": "Payment processed but order update failed", "detail": msg},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Clear cart
        try:
            Cart.objects.filter(customer=request.user).delete()
        except Exception:
            pass

        return Response(
            {"status": "success", "order": OrderSerializer(payment.order).data}
        )

# =========================================================
# Orders ViewSet
# =========================================================


class IsOrderOwnerOrStaff(permissions.BasePermission):
    """
    Customer apne hi orders dekh sakta hai.
    Staff sab dekh sakte hain.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return getattr(obj, "customer_id", None) == request.user.id


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """
    - GET /orders/       => list (My Orders)
    - GET /orders/<id>/  => detail
    - POST /orders/<id>/cancel/  => cancel order
    """

    permission_classes = [permissions.IsAuthenticated, IsOrderOwnerOrStaff]
    queryset = (
        Order.objects.select_related("customer", "warehouse")
        .prefetch_related("items", "timeline")
        .all()
    )

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(customer=user)

    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
        permission_classes=[permissions.IsAuthenticated, IsOrderOwnerOrStaff],
    )
    def cancel(self, request, pk=None):
        """
        Customer/OPS order cancel kar sakte hain.

        - Already delivered/cancelled => 400
        - Paid order => refund signal trigger hota hai (payments app mein handle)
        """
        order = self.get_object()
        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data.get("reason", "")

        ok, msg = cancel_order(order, cancelled_by=request.user, reason=reason)
        if not ok:
            return Response(
                {"error": msg or "Unable to cancel order"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.refresh_from_db()
        return Response(OrderSerializer(order).data, status=status.HTTP_200_OK)

class CancelOrderView(APIView):
    """
    Customer-initiated order cancellation.

    POST /api/v1/orders/<order_id>/cancel/
    body: { "reason": "optional string" }

    Rules:
    - Only the owning customer can cancel
    - Status must NOT be delivered/cancelled
    - Optional time-window check (ORDER_CANCELLATION_WINDOW in seconds)
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, pk):
        user = request.user
        reason = request.data.get("reason", "")

        # 1. Get order owned by this customer
        order = get_object_or_404(Order, id=pk, customer=user)

        # 2. Check basic status guard
        if order.status in ["delivered", "cancelled"]:
            return Response(
                {"error": "Order cannot be cancelled in its current state."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Optional cancellation time window
        window_seconds = getattr(settings, "ORDER_CANCELLATION_WINDOW", 300)
        cutoff = order.created_at + timedelta(seconds=window_seconds)
        if timezone.now() > cutoff:
            return Response(
                {"error": "Cancellation window has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Delegate to service
        ok, msg = cancel_order(order, cancelled_by="CUSTOMER", reason=reason)
        if not ok:
            return Response(
                {"error": msg or "Unable to cancel order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "status": "cancelled",
                "order_id": str(order.id),
                "message": "Order cancelled successfully.",
            },
            status=status.HTTP_200_OK,
        )
