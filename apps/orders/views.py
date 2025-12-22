from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from .models.cart import Cart, CartItem
from .models.order import Order
from .serializers import CartSerializer, OrderSerializer
from .services import OrderService
from apps.catalog.models import Product


from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.cache import cache

from apps.utils.views import BaseViewSet
from .models import Order, Cart
from .serializers import OrderSerializer, CartSerializer
from .services import OrderService
from apps.utils.exceptions import BusinessValidationError

class CheckoutViewSet(BaseViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def process_checkout(self, request):
        """
        Main checkout endpoint.
        
        SEQUENCE:
        1. Idempotency Check (Redis)
        2. Cart Validation
        3. Atomic Transaction (Order Creation + Stock Reservation)
        4. Payment Initialization
        """
        
        # 1. Idempotency Check
        idempotency_key = request.headers.get('X-Idempotency-Key')
        if not idempotency_key:
            return Response(
                {"error": "X-Idempotency-Key header is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        cache_key = f"checkout_idempotency_{request.user.id}_{idempotency_key}"
        if cache.get(cache_key):
             return Response(
                {"error": "Duplicate request detected"}, 
                status=status.HTTP_409_CONFLICT
            )
            
        # Lock this key for 60 seconds to prevent rapid double-clicks
        cache.set(cache_key, "processing", timeout=60)

        try:
            # Data extraction
            cart_id = request.data.get('cart_id')
            payment_method = request.data.get('payment_method', 'RAZORPAY')
            address_id = request.data.get('address_id')
            
            # 2. & 3. Atomic Order Creation (Delegated to Service)
            # This service method already contains the transaction.atomic() and select_for_update() logic
            order = OrderService.create_order_from_cart(
                user=request.user, 
                cart_id=cart_id, 
                payment_method=payment_method, 
                address_id=address_id
            )
            
            # 4. Payment Initialization (Mock for now, would be Razorpay integration)
            payment_data = {
                "order_id": order.order_id,
                "amount": order.total_amount,
                "currency": "INR",
                # "payment_link": ... (Razorpay logic would go here)
            }
            
            return Response({
                "status": "success",
                "message": "Order created successfully",
                "data": {
                    "order": OrderSerializer(order).data,
                    "payment": payment_data
                }
            }, status=status.HTTP_201_CREATED)
            
        except BusinessValidationError as e:
            cache.delete(cache_key) # Release lock on business failure
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            cache.delete(cache_key) # Release lock on system failure
            # Log the full exception here
            return Response(
                {"error": "Checkout failed due to a system error. Please try again."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CartViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add_item(self, request):
        product_id = request.data.get('product_id')
        qty = int(request.data.get('quantity', 1))
        
        cart, _ = Cart.objects.get_or_create(user=request.user)
        product = Product.objects.get(id=product_id)
        
        item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if not created:
            item.quantity += qty
        else:
            item.quantity = qty
        item.save()
        
        return Response(CartSerializer(cart).data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart.items.all().delete()
        return Response({"status": "cleared"})

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    def create(self, request):
        """
        Checkout Endpoint.
        Expects: { "address_id": 1, "lat": 12.97, "lng": 77.59 }
        """
        address_id = request.data.get('address_id')
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        
        try:
            order = OrderService.create_order_from_cart(
                user=request.user,
                address_id=address_id,
                lat=lat,
                lng=lng
            )
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)