# apps/orders/views.py
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import IsCustomer
from apps.catalog.models import SKU
from .models import Order, OrderItem, OrderTimeline
from .serializers import (
    CreateOrderSerializer,
    OrderSerializer,
    OrderListSerializer
)
from apps.inventory.services import check_and_lock_inventory
from .serializers import CartSerializer, AddToCartSerializer # <-- Import new serializers
from .models import Cart, CartItem
from .signals import order_refund_requested  # <-- Decoupled Signal Import

import logging
logger = logging.getLogger(__name__)


class CreateOrderAPIView(APIView):
    """
    Naya order create karne ke liye main API.
    Yeh sirf order ko "pending" state mein banayega.
    POST /api/v1/orders/create/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = serializer.validated_data
        items_data = validated_data.pop('items')
        
        try:
            # Step 1: Database transaction shuru karein
            with transaction.atomic():
                
                # Step 2: Order ki keemat (Pricing) calculate karein
                total_amount = 0
                order_items_to_create = []
                warehouse_id = validated_data['warehouse_id']

                for item_data in items_data:
                    sku_id = item_data['sku_id']
                    quantity = item_data['quantity']
                    
                    # --- FIX: Stock Check & Lock (Race Condition Prevention) ---
                    # Order create karne se pehle check karo ki maal hai ya nahi
                    check_and_lock_inventory(
                        warehouse_id=warehouse_id,
                        sku_id=sku_id,
                        qty_needed=quantity
                    )
                    # -----------------------------------------------------------
                    
                    # SKU se asli price fetch karein
                    sku = SKU.objects.get(id=sku_id)
                    unit_price = sku.sale_price 
                    
                    item_total = unit_price * quantity
                    total_amount += item_total
                    
                    # OrderItem object ko create list mein add karein
                    order_items_to_create.append(
                        OrderItem(
                            sku_id=sku_id,
                            quantity=quantity,
                            unit_price=unit_price,
                        )
                    )

                # Step 3: Order object banayein (Pending state mein)
                order = Order.objects.create(
                    customer=request.user,
                    warehouse_id=warehouse_id,
                    delivery_address_json=validated_data['delivery_address_json'],
                    delivery_lat=validated_data.get('delivery_lat'),
                    delivery_lng=validated_data.get('delivery_lng'),
                    status="pending",
                    payment_status="pending",
                    total_amount=total_amount,
                    discount_amount=0, 
                    final_amount=total_amount
                )
                
                # Step 4: Order items ko Order se link karke bulk create karein
                for item in order_items_to_create:
                    item.order = order
                OrderItem.objects.bulk_create(order_items_to_create)
                
                # Step 5: Order ki history (timeline) mein pehli entry daalein
                OrderTimeline.objects.create(
                    order=order,
                    status="pending",
                    notes="Order created and awaiting payment."
                )

            # Step 6: Customer ko Order ID aur Amount waapas bhejein
            response = Response({
                "order_id": order.id,
                "final_amount": order.final_amount,
                "status": order.status,
                "payment_status": order.payment_status,
            }, status=status.HTTP_201_CREATED)

            # --- FIX: Idempotency Middleware ke liye Header ---
            # Yeh header batata hai ki is response ko cache/save karna hai
            response['X-STORE-IDEMPOTENCY'] = '1'
            return response

        except Exception as e:
            logger.exception(f"Order creation failed for user {request.user.id}: {e}")
            # Agar Out of stock error aata hai inventory service se, toh wahi message dikhao
            error_message = str(e)
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            if "Insufficient stock" in error_message:
                status_code = status.HTTP_400_BAD_REQUEST

            return Response(
                {"detail": f"Order creation failed: {error_message}"}, 
                status=status_code
            )

class OrderHistoryAPIView(generics.ListAPIView):
    """
    Customer ke puraane orders ki list.
    GET /api/v1/orders/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)


class OrderDetailAPIView(generics.RetrieveAPIView):
    """
    Ek specific order ki poori detail.
    GET /api/v1/orders/<uuid:id>/
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = OrderSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).prefetch_related(
            'items__sku', 'timeline'
        )


class CancelOrderAPIView(APIView):
    """
    Customer khud order cancel kar sake.
    POST /api/v1/orders/<id>/cancel/
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, id):
        order = get_object_or_404(Order, id=id, customer=request.user)
        
        if order.status not in ['pending', 'confirmed']:
            return Response(
                {"detail": "Cannot cancel order at this stage (already processing)."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                order.status = 'cancelled'
                order.save(update_fields=['status'])
                
                OrderTimeline.objects.create(
                    order=order, 
                    status='cancelled', 
                    notes="Cancelled by customer."
                )
                
                # --- AUTO REFUND LOGIC (Via Signal) ---
                if order.payment_status == 'paid':
                    order_refund_requested.send(
                        sender=Order, 
                        order_id=order.id, 
                        amount=order.final_amount, 
                        reason="Cancelled by customer."
                    )
                    logger.info(f"Refund request signal sent for cancelled order {order.id}.")
                # --------------------------------------

            return Response({"status": "Order cancelled and refund initiated if applicable."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error cancelling order {order.id}: {e}")
            return Response({"detail": "Failed to cancel order."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class ManageCartAPIView(APIView):
    """
    Single endpoint to Get, Add, Update, or Clear Cart.
    GET  /api/v1/orders/cart/       -> View Cart
    POST /api/v1/orders/cart/       -> Add/Update Item {sku_id, quantity}
    DELETE /api/v1/orders/cart/     -> Clear entire Cart
    """
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_cart(self, user):
        cart, _ = Cart.objects.get_or_create(customer=user)
        return cart

    def get(self, request):
        cart = self.get_cart(request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def post(self, request):
        """
        Item Add ya Update karne ke liye. 
        Agar quantity 0 bheji, toh item remove ho jayega.
        """
        serializer = AddToCartSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        sku_id = serializer.validated_data['sku_id']
        quantity = serializer.validated_data['quantity']
        cart = self.get_cart(request.user)

        # Check SKU valid hai ya nahi
        try:
            sku = SKU.objects.get(id=sku_id, is_active=True)
        except SKU.DoesNotExist:
            return Response({"detail": "Product not found or inactive."}, status=status.HTTP_404_NOT_FOUND)

        # Logic: Add, Update or Remove
        try:
            item = CartItem.objects.get(cart=cart, sku=sku)
            if quantity == 0:
                item.delete()
            else:
                item.quantity = quantity
                item.save()
        except CartItem.DoesNotExist:
            if quantity > 0:
                CartItem.objects.create(cart=cart, sku=sku, quantity=quantity)

        # Return updated cart
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)

    def delete(self, request):
        """
        Poora cart khali karne ke liye.
        """
        cart = self.get_cart(request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)