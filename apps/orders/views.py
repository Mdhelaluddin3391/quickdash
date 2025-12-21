import logging
import razorpay
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserAddress
from apps.orders.models import Order, Cart, CartItem
from apps.orders.serializers import (
    CreateOrderSerializer, OrderSerializer, OrderListSerializer,
    CartSerializer, AddToCartSerializer, PaymentVerificationSerializer
)
from apps.orders.services import (
    CheckoutOrchestrator,
    process_successful_payment,
    cancel_order
)
from apps.accounts.permissions import IsCustomer
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

# This key must match what is used in apps/warehouse/views.py
SERVICE_WAREHOUSE_KEY = 'quickdash_service_warehouse_id'

class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        cart, _ = Cart.objects.prefetch_related('items__sku').get_or_create(customer=request.user)
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
            item.save()

        cart = Cart.objects.prefetch_related('items__sku').get(id=cart.id)
        return Response(CartSerializer(cart).data)

class CheckoutView(APIView):
    """
    Main checkout entry point.
    Handles Validation -> Warehouse Selection -> Stock Lock -> Order Creation -> Payment Init
    """
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def post(self, request):
        # 1. Enforce Serviceability Check from Session
        warehouse_id = request.session.get(SERVICE_WAREHOUSE_KEY)
        
        # 2. Serialize Data
        serializer = CreateOrderSerializer(
            data=request.data,
            context={"request": request, "session_warehouse_id": warehouse_id}
        )
        serializer.is_valid(raise_exception=True)

        # 3. Inject Validated Data into Orchestrator
        # We ensure the orchestrator gets the warehouse ID from session if not in body
        validated_data = serializer.validated_data
        if not validated_data.get("warehouse_id") and warehouse_id:
            validated_data["warehouse_id"] = warehouse_id

        orchestrator = CheckoutOrchestrator(request.user, validated_data)
        order, payment_data, error = orchestrator.execute()

        if error:
            return Response({"error": error}, status=400)

        # 4. Success Response
        if payment_data and payment_data.get("mode") == "COD":
            ok, msg = process_successful_payment(order)
            if not ok:
                return Response({"error": msg}, status=500)
            
            return Response({
                "order": OrderSerializer(order).data,
                "payment": payment_data
            }, status=201)

        return Response({
            "order_id": str(order.id),
            **payment_data
        }, status=201)

# Backwards compatibility alias
CreateOrderAPIView = CheckoutView 

class PaymentVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PaymentVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        
        try:
            client.utility.verify_payment_signature(data)
        except razorpay.errors.SignatureVerificationError:
            return Response({"error": "Invalid signature"}, status=400)
        except Exception as e:
            logger.error(f"Payment Verification Error: {e}")
            return Response({"error": "System error"}, status=500)

        payment = get_object_or_404(Payment, gateway_order_id=data["razorpay_order_id"])
        
        if payment.status == Payment.PaymentStatus.SUCCESSFUL:
             return Response({"status": "success", "message": "Already processed"})

        payment.transaction_id = data["razorpay_payment_id"]
        payment.save()

        process_successful_payment(payment.order)
        return Response({"status": "success"})

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
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
        ok, msg = cancel_order(order, cancelled_by="CUSTOMER", reason=request.data.get("reason", ""))
        if not ok: return Response({"error": msg}, status=400)
        return Response(OrderSerializer(order).data)